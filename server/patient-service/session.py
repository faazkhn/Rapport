"""WebSocket voice session (PROTOCOL.md): mic PCM in -> VAD -> STT -> streamed LLM -> per-sentence TTS -> PCM out.

One Session per connection. Audio stays in memory. Every stage is timed in ms and sent as a `timing` event.
"""
import asyncio
import contextlib
import io
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import jsonschema
import numpy as np

import brain
import stream
import stt

log = logging.getLogger("patient-service")
TTS_MODEL = "KittenML/kitten-tts-mini-0.8"
VOICES = ["Bella", "Luna", "Rosie", "Kiki", "Jasper", "Bruno", "Hugo", "Leo"]
OUT_SR = 24000
PRE_ROLL_FRAMES = 10  # ~320 ms of audio kept before VAD start so the first word is not clipped
PRESSURED_OVERLAP_S = 1.5  # pressured_speech: keep talking over the doctor for 1-2 s (DESIGN 7.1)
TTS = {"model": None}
# MLX and the ONNX TTS each get one dedicated thread
STT_POOL = ThreadPoolExecutor(1, thread_name_prefix="stt")
TTS_POOL = ThreadPoolExecutor(1, thread_name_prefix="tts")


def synth(text: str, voice: str, speed: float) -> np.ndarray:
    # kittenml prints the input text to stdout; keep learner/patient text out of logs.
    # shortcut: redirect_stdout is process-wide, so concurrent prints are swallowed too; fine for one client.
    with contextlib.redirect_stdout(io.StringIO()):
        return TTS["model"].generate(text, voice=voice, speed=speed)


def tts_speed(case: dict, state: dict) -> float:
    base = case["patient"].get("voice_speed", 1.0)
    slowed, pressured = brain.cue_live(case, "slowed", state), brain.cue_live(case, "pressured_speech", state)
    speed = base + (min(base, 0.85) - base) * slowed  # Unity SpeechTiming.TtsSpeed
    return speed + (1.3 - speed) * pressured


def ms(a, b):
    return None if a is None or b is None else round((b - a) * 1000)


class Session:
    def __init__(self, send_json, send_bytes, llm_client=None, tts_fn=None, stt_fn=None):
        self.send_json, self.send_bytes = send_json, send_bytes
        self.client = llm_client  # None = brain.get_client()
        self.tts_fn = tts_fn or synth
        self.stt_fn = stt_fn or stt.transcribe
        self.case = None
        self.state = None
        self.messages = []
        self.t_start = time.monotonic()
        self.hands_free = True
        self.ptt = False
        self.vad = None
        self.pending = b""
        self.pre_roll = []
        self.speech = None  # list of frames while the doctor is talking
        self.turn_task = None
        self.cancel = threading.Event()
        self.playing_until = 0.0  # monotonic time the client should finish playing what we sent
        self.interrupted = False
        self.turn_no = 0

    # ---------- incoming ----------

    async def on_json(self, msg: dict):
        t = msg.get("type")
        if t == "start":
            await self.start(msg)
        elif self.case is None:
            await self.send_json({"type": "error", "error": "send start first"})
        elif t == "text":
            await self.begin_turn(str(msg.get("text", ""))[:4000], {"input": "text", "t_end": time.monotonic()})
        elif t == "ptt_begin":
            self.ptt = True
            await self.on_speech_start()
            self.speech = list(self.pre_roll)
        elif t == "ptt_end":
            self.ptt = False
            if self.speech:
                frames, self.speech = self.speech, None
                await self.end_speech(frames, time.monotonic(), time.monotonic())
        elif t == "hands_free":
            self.hands_free = bool(msg.get("on", True))
            self.speech = None
            self.vad.reset()
        elif t == "stop":
            await self.stop("client")
        else:
            await self.send_json({"type": "error", "error": f"unknown type {t!r}"})

    async def start(self, msg):
        try:
            self.case = brain.load_case(msg["case_id"], msg.get("variant", "female"))
        except (KeyError, FileNotFoundError) as e:
            await self.send_json({"type": "error", "error": f"bad case_id/variant: {e}"})
            return
        self.state = {**self.case["state_start"], **(msg.get("state") or {})}
        self.messages, self.t_start = [], time.monotonic()
        self.hands_free = bool(msg.get("hands_free", True))
        self.vad = stt.Vad(int(msg.get("vad_silence_ms", stt.SILENCE_MS)))
        p = self.case["patient"]
        await self.send_json({"type": "session", "case_id": self.case["id"], "variant": self.case["variant"], "name": p["name"],
                              "model_id": p["model_id"], "voice_id": p["voice_id"], "state": self.state,
                              "in_rate": stt.SR, "out_rate": OUT_SR, "llm": brain.default_model()})
        asyncio.get_running_loop().run_in_executor(None, self.warm)
        await self.send_json({"type": "listening"})

    def warm(self):
        """Fill slot 0's KV cache with this case+variant's fixed prefix so the first turn is fast."""
        with contextlib.suppress(Exception):
            kw = brain.llm_kwargs(brain.default_model(), brain.build_messages(self.case, self.state, [{"role": "doctor", "text": "Hello."}]),
                                  {"type": "object"}, "warm", 0)
            kw.pop("response_format")
            (self.client or brain.get_client()).chat.completions.create(**{**kw, "max_tokens": 1})

    async def on_audio(self, data: bytes):
        if self.case is None:
            return
        self.pending += data
        n = stt.FRAME * 2
        while len(self.pending) >= n:
            frame, self.pending = stt.pcm16_to_float(self.pending[:n]), self.pending[n:]
            await self.on_frame(frame)

    async def on_frame(self, frame):
        ev = self.vad.feed(frame)
        if self.ptt:
            self.speech.append(frame)
            if ev == "start":
                await self.on_speech_start()
            return
        if not self.hands_free:
            return
        if self.speech is None:
            self.pre_roll = (self.pre_roll + [frame])[-PRE_ROLL_FRAMES:]
            if ev == "start":
                self.speech = list(self.pre_roll)
                await self.on_speech_start()
            return
        self.speech.append(frame)
        if ev == "end":
            now = time.monotonic()
            # wall time the doctor actually stopped = now minus the trailing silence already received
            t_end = now - (self.vad.samples - self.vad.end_sample) / stt.SR
            frames, self.speech = self.speech, None
            await self.end_speech(frames, t_end, now)

    async def on_speech_start(self):
        await self.send_json({"type": "vad_start"})
        if self.is_speaking():
            await self.barge_in()

    def is_speaking(self) -> bool:
        return (self.turn_task is not None and not self.turn_task.done()) or time.monotonic() < self.playing_until

    async def barge_in(self):
        if brain.cue_live(self.case, "pressured_speech", self.state) > 0.1:
            async def later():  # talks over the doctor briefly; a task so mic frames keep flowing
                await asyncio.sleep(PRESSURED_OVERLAP_S)
                await self.stop("barge_in")
            asyncio.create_task(later())
        else:
            await self.stop("barge_in")

    async def stop(self, reason):
        t = time.monotonic()
        self.cancel.set()
        self.playing_until = 0.0
        if reason == "barge_in":
            self.interrupted = True
        await self.send_json({"type": "stop", "reason": reason})
        log.info("stop reason=%s service_ms=%d", reason, ms(t, time.monotonic()))

    async def end_speech(self, frames, t_end, t_detect):
        audio = np.concatenate(frames) if frames else np.zeros(0, np.float32)
        loop = asyncio.get_running_loop()
        t0 = time.monotonic()
        text = await loop.run_in_executor(STT_POOL, self.stt_fn, audio)
        timing = {"input": "voice", "t_end": t_end, "vad_endpoint_ms": ms(t_end, t_detect), "stt_ms": ms(t0, time.monotonic()),
                  "speech_s": round(len(audio) / stt.SR, 2)}
        if not text.strip():
            await self.send_json({"type": "transcript", "text": "", "final": True})
            await self.send_json({"type": "listening"})
            return
        await self.begin_turn(text, timing)

    # ---------- the turn ----------

    async def begin_turn(self, text: str, timing: dict):
        if not text.strip():
            return
        if self.is_speaking():
            await self.stop("barge_in")
        if self.turn_task and not self.turn_task.done():
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self.turn_task
        await self.send_json({"type": "transcript", "text": text, "final": True})
        self.cancel = threading.Event()
        self.turn_task = asyncio.create_task(self.run_turn(text, timing, self.cancel))

    async def run_turn(self, text, timing, cancel):
        loop = asyncio.get_running_loop()
        case, state = self.case, dict(self.state)
        self.turn_no += 1
        elapsed = (time.monotonic() - self.t_start) / 60
        self.messages.append({"role": "doctor", "text": text})
        prev = next((m["text"] for m in reversed(self.messages[:-1]) if m["role"] == "patient"), None)
        model = brain.default_model()
        await self.send_json({"type": "thinking"})

        intents_fut = loop.run_in_executor(None, brain.tag_intents, text, prev, self.client, model)
        allowed = [f["id"] for f in brain.allowed_facts(case, state["trust"])]
        schema = brain.build_reply_schema(case, allowed, brain.allowed_actions(case, state["trust"]))
        kw = brain.llm_kwargs(model, brain.build_messages(case, state, self.messages, elapsed_min=elapsed),
                              schema, "patient_reply", 0)
        q: asyncio.Queue = asyncio.Queue()
        t_llm = time.monotonic()
        loop.run_in_executor(None, self._llm_stream, kw, q, loop, cancel)

        pause = brain.slowed_pause_s(case, state)
        speed = tts_speed(case, state)
        voice = case["patient"]["voice_id"]
        parser, splitter = stream.UtteranceStream(), stream.SentenceSplitter()
        spoken, dropped_banned, idx = [], [], 0
        marks = {"ttft": None, "first_sentence": None, "tts_first_ms": None, "audio_start": None}
        err = None

        async def speak(sentence):
            nonlocal idx
            sentence, hits = brain.strip_banned(sentence, case["banned_words"])
            dropped_banned.extend(hits)
            if not sentence or cancel.is_set():
                return
            t = time.monotonic()
            audio = await loop.run_in_executor(TTS_POOL, self.tts_fn, sentence, voice, speed)
            if cancel.is_set():
                return
            if marks["audio_start"] is None:
                marks["tts_first_ms"] = ms(t, time.monotonic())
                marks["audio_start"] = time.monotonic()
                await self.send_json({"type": "speaking", "slowed_pause_ms": round(pause * 1000)})
                if pause:
                    await asyncio.sleep(pause)  # deliberate `slowed` pause, logged separately, not lag
                    if cancel.is_set():
                        return
            pcm = stt.float_to_pcm16(np.asarray(audio, dtype=np.float32))
            dur = len(pcm) / 2 / OUT_SR
            await self.send_json({"type": "sentence", "index": idx, "text": sentence, "samples": len(pcm) // 2})
            await self.send_bytes(pcm)
            self.playing_until = max(self.playing_until, time.monotonic()) + dur
            spoken.append(sentence)
            idx += 1

        while True:
            kind, val = await q.get()
            if kind == "chunk":
                if marks["ttft"] is None:
                    marks["ttft"] = time.monotonic()
                for s in splitter.feed(parser.feed(val)):
                    marks["first_sentence"] = marks["first_sentence"] or time.monotonic()
                    await speak(s)
            elif kind == "error":
                err = val
                break
            else:
                break
        if not cancel.is_set():
            for s in splitter.flush():
                marks["first_sentence"] = marks["first_sentence"] or time.monotonic()
                await speak(s)
        t_done = time.monotonic()
        tagged = await intents_fut
        if self.interrupted:  # the doctor talked over the previous reply
            tagged, self.interrupted = tagged + ["interrupt"], False

        meta = {"model": model, "allowed_fact_ids": allowed, "fallback": False, "guard_dropped": []}
        try:
            if err:
                raise RuntimeError(err)
            raw = parser.full()
            jsonschema.validate(raw, schema)
            reply, meta["guard_dropped"] = brain.guard({**raw, "doctor_intents": tagged}, case, state["trust"])
        except Exception as e:
            meta.update(fallback=True, errors=[type(e).__name__])
            reply = {**brain.fallback_reply(case), "doctor_intents": tagged}
            if not spoken and not cancel.is_set():
                await speak(reply["utterance"])
        reply["utterance"] = " ".join(spoken) if spoken else reply["utterance"]
        if cancel.is_set():
            meta["barge_in"] = True
            reply["utterance"] = (" ".join(spoken) + "...") if spoken else ""
        if reply["utterance"]:
            self.messages.append({"role": "patient", "text": reply["utterance"]})
        self.state = brain.apply_turn(state, reply)
        await self.send_json({"type": "intents", "doctor_intents": tagged})
        await self.send_json({"type": "reply", "turn": self.turn_no, "reply": reply, "state": self.state, "meta": meta})

        t_end = timing.pop("t_end")
        timing.update({
            "type": "timing", "turn": self.turn_no,
            "llm_ttft_ms": ms(t_llm, marks["ttft"]), "llm_first_sentence_ms": ms(t_llm, marks["first_sentence"]),
            "llm_total_ms": ms(t_llm, t_done), "tts_first_chunk_ms": marks["tts_first_ms"],
            "audio_start_ms": ms(t_end, marks["audio_start"]),  # end of doctor speech -> first patient audio, excluding pause
            "slowed_pause_ms": round(pause * 1000), "banned_dropped": dropped_banned,
        })
        await self.send_json(timing)
        log.info("turn %d timing %s", self.turn_no, json.dumps({k: v for k, v in timing.items() if k.endswith("_ms")}))
        await self.send_json({"type": "listening"})

    def _llm_stream(self, kw, q, loop, cancel):
        put = lambda *x: loop.call_soon_threadsafe(q.put_nowait, x)  # noqa: E731
        try:
            for attempt in range(2):  # retry once only if nothing came back
                got = False
                resp = (self.client or brain.get_client()).chat.completions.create(**kw, stream=True)
                for ch in resp:
                    if cancel.is_set():
                        resp.close()
                        break
                    d = ch.choices[0].delta.content if ch.choices else None
                    if d:
                        got = True
                        put("chunk", d)
                if got or cancel.is_set():
                    break
            put("done", None)
        except Exception as e:
            put("error", type(e).__name__)


async def serve(ws):
    """FastAPI WebSocket handler."""
    from fastapi import WebSocketDisconnect
    await ws.accept()
    s = Session(ws.send_json, ws.send_bytes)
    try:
        while True:
            m = await ws.receive()
            if m["type"] == "websocket.disconnect":
                break
            if m.get("bytes") is not None:
                await s.on_audio(m["bytes"])
            elif m.get("text") is not None:
                try:
                    msg = json.loads(m["text"])
                except ValueError:
                    await ws.send_json({"type": "error", "error": "bad json"})
                    continue
                await s.on_json(msg)
    except WebSocketDisconnect:
        pass
    finally:
        s.cancel.set()
