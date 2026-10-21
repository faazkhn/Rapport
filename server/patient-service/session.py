"""WebSocket voice session (PROTOCOL.md): mic PCM in -> VAD -> STT -> streamed LLM -> per-sentence TTS -> PCM out.

One Session per connection. Audio stays in memory. Every stage is timed in ms and sent as a `timing` event.
"""
import asyncio
import contextlib
import io
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import jsonschema
import numpy as np

import brain
import staged
import stream
import stt
import twin
import voice
import twin_bus

log = logging.getLogger("patient-service")
TTS_MODEL = "KittenML/kitten-tts-mini-0.8"
VOICES = ["Bella", "Luna", "Rosie", "Kiki", "Jasper", "Bruno", "Hugo", "Leo"]
OUT_SR = 24000
PRE_ROLL_FRAMES = 10  # ~320 ms of audio kept before VAD start so the first word is not clipped
TURN_CAP_MS = 1200  # Smart Turn says "not finished": end the turn anyway after this much silence (old 500 ms + 700)
SMART_TURN_DONE = 0.5
SMART = {"model": None}  # stt.SmartTurn loaded at startup, or None
PRESSURED_OVERLAP_S = 1.5  # pressured_speech: keep talking over the doctor for 1-2 s (DESIGN 7.1)
TTS = {"model": None, "backend": None}  # backend: voice.load(RAPPORT_TTS) at startup; None = KittenTTS
TWIN_LOG_DIR = Path(os.environ.get("RAPPORT_TWIN_LOG_DIR") or brain.REPO_ROOT / "logs" / "twin")  # local only, git-ignored
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
    speed = base + (min(base, 0.9) - base) * slowed  # Unity SpeechTiming.TtsSpeed
    return speed + (1.3 - speed) * pressured


def ms(a, b):
    return None if a is None or b is None else round((b - a) * 1000)


class Session:
    def __init__(self, send_json, send_bytes, llm_client=None, tts_fn=None, stt_fn=None):
        self.send_json, self.send_bytes = send_json, send_bytes
        self.client = llm_client  # None = brain.get_client()
        self.tts_fn = tts_fn or synth
        self.fallback = voice.FnBackend(self.tts_fn)
        self.tts = self.fallback if tts_fn else (TTS["backend"] or self.fallback)
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
        self.held = None  # a pause that may end the turn: {"t_end", "spec": speculative STT future}
        self.smart_turn = SMART["model"]
        self.silence_ms = stt.SILENCE_MS
        self.turn_task = None
        self.cancel = threading.Event()
        self.playing_until = 0.0  # monotonic time the client should finish playing what we sent
        self.interrupted = False
        self.turn_no = 0
        self.staged = None  # staged.Script in RAPPORT_STAGED concept-preview mode
        self.mood = None  # Digital Twin PAD mood, set at start
        self.next_speed = 1.0  # expression-map speed factor from the last reply, applied to the next one
        self.twin_log = None  # this session's Twin event log (JSONL)

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
            self.drop_held()
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
            self.drop_held()
            self.vad.reset()
        elif t == "stop":
            await self.stop("client")
        elif t == "state":  # client-side drift (case state_drift_per_min); clamped, unknown keys ignored
            st = msg.get("state") or {}
            self.state.update({k: min(100.0, max(0.0, float(st[k]))) for k in brain.STATE_KEYS if k in st})
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
        self.silence_ms = int(msg.get("vad_silence_ms", stt.SILENCE_MS))
        self.vad = stt.Vad(min(stt.SPECULATE_MS, self.silence_ms))  # the end event is a candidate; on_frame decides
        if hasattr(self.tts, "seed"):  # one fixed speaker per variant
            self.tts.seed = voice.QwenDesign.SEEDS.get(self.case["variant"], 1234)
        p = self.case["patient"]
        await self.send_json({"type": "session", "case_id": self.case["id"], "variant": self.case["variant"], "name": p["name"],
                              "model_id": p["model_id"], "voice_id": p["voice_id"], "state": self.state,
                              "in_rate": stt.SR, "out_rate": OUT_SR, "llm": brain.default_model(), "staged": staged.enabled()})
        self.mood, self.next_speed = twin.pad_from(self.state), 1.0
        if staged.enabled():
            self.staged = staged.Script(self.case["variant"], OUT_SR)
        else:
            try:
                TWIN_LOG_DIR.mkdir(parents=True, exist_ok=True)
                self.twin_log = TWIN_LOG_DIR / f"{time.strftime('%Y%m%d_%H%M%S')}_{self.case['id']}.jsonl"
            except OSError as e:  # the log is a convenience; never let it stop the voice
                log.warning("twin log off: %s", type(e).__name__)
                self.twin_log = None
            await self.twin(twin.init_event(self.case, self.state))
            asyncio.get_running_loop().run_in_executor(None, self.warm)
        await self.send_json({"type": "listening"})

    async def twin(self, msg: dict):
        """A Twin event or snapshot: to this client, to Twin view viewers, and to the session's Twin log."""
        await self.send_json(msg if msg.get("type") == "brain_snapshot" else {"type": "twin_event", **msg})
        e = ({**msg, "type": "snapshot"} if msg.get("type") == "brain_snapshot"
             else {"type": msg["event"], **{k: v for k, v in msg.items() if k != "event"}})
        e["t"] = round(time.monotonic() - self.t_start, 2)
        twin_bus.publish(e)
        if self.twin_log:
            try:
                with open(self.twin_log, "a", encoding="utf-8") as f:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
            except OSError as err:  # full or unwritable disk: drop the log, keep the voice
                log.warning("twin log off: %s", type(err).__name__)
                self.twin_log = None

    def warm(self):
        """Prefill slot 0's KV cache with the next turn's prompt up to the doctor's words (system, facts block for the current trust,
        history), so only the doctor's line and the small tail are left when they stop talking. Run at start and after every reply:
        a trust change rewrites the facts block near the start, and Gemma's sliding-window cache cannot reuse what follows it."""
        if brain.use_grok():
            return
        with contextlib.suppress(Exception):
            msgs = self.messages + [{"role": "doctor", "text": ""}]
            kw = brain.llm_kwargs(brain.default_model(), brain.build_messages(self.case, self.state, msgs), {"type": "object"}, "warm", 0)
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
        if ev == "start":
            self.drop_held()  # the doctor kept talking: the speculative transcript is stale
        elif ev == "end":
            loop = asyncio.get_running_loop()
            audio = np.concatenate(self.speech)
            # wall time the doctor actually stopped = now minus the trailing silence already received
            t_end = time.monotonic() - (self.vad.samples - self.vad.end_sample) / stt.SR
            spec = None if self.staged else loop.run_in_executor(STT_POOL, self.stt_fn, audio)
            self.held = {"t_end": t_end, "spec": spec, "p": None}
            if self.smart_turn:
                self.held["p"] = p = await loop.run_in_executor(None, self.smart_turn.complete, audio)
                if p >= SMART_TURN_DONE:
                    return await self.end_held()
        if self.held:
            cap = TURN_CAP_MS if self.smart_turn else self.silence_ms
            if (self.vad.samples - self.vad.end_sample) * 1000 >= cap * stt.SR:
                await self.end_held()

    def drop_held(self):
        if self.held and self.held["spec"]:
            self.held["spec"].cancel()  # frees the single STT thread if the job hasn't started
        self.held = None

    async def end_held(self):
        held, frames, self.held, self.speech = self.held, self.speech, None, None
        await self.end_speech(frames, held["t_end"], time.monotonic(), held["spec"], held["p"])

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

    async def end_speech(self, frames, t_end, t_detect, spec=None, p_complete=None):
        audio = np.concatenate(frames) if frames else np.zeros(0, np.float32)
        loop = asyncio.get_running_loop()
        t0 = time.monotonic()
        if self.staged:
            text = self.staged.doctor_line()
        else:  # stt_ms is only the wait left after the endpoint when the speculative transcript was already running
            text = await (spec or loop.run_in_executor(STT_POOL, self.stt_fn, audio))
        timing = {"input": "voice", "t_end": t_end, "vad_endpoint_ms": ms(t_end, t_detect), "stt_ms": ms(t0, time.monotonic()),
                  "speech_s": round(len(audio) / stt.SR, 2), "smart_turn": p_complete, "speculative_stt": spec is not None}
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
        if self.staged:
            return await self.run_staged_turn(text, timing, cancel)
        loop = asyncio.get_running_loop()
        case, state = self.case, dict(self.state)
        self.turn_no += 1
        was_interrupted, self.interrupted = self.interrupted, False  # the doctor talked over the previous reply
        elapsed = (time.monotonic() - self.t_start) / 60
        self.messages.append({"role": "doctor", "text": text})
        prev = next((m["text"] for m in reversed(self.messages[:-1]) if m["role"] == "patient"), None)
        model = brain.default_model()
        await self.twin({"event": "doctor_end", "turn": self.turn_no})
        await self.send_json({"type": "thinking"})

        recalled = twin.recall(case, state["trust"], text)
        allowed = [f["id"] for f in brain.allowed_facts(case, state["trust"])]
        schema = brain.build_reply_schema(case, allowed, brain.allowed_actions(case, state["trust"]))
        kw = brain.llm_kwargs(model, brain.build_messages(case, state, self.messages, elapsed_min=elapsed, recalled=recalled),
                              schema, "patient_reply", 0)
        q: asyncio.Queue = asyncio.Queue()
        t_llm = time.monotonic()
        loop.run_in_executor(None, self._llm_stream, kw, q, loop, cancel)

        pause = brain.slowed_pause_s(case, state)
        speed = tts_speed(case, state) * self.next_speed
        voice_id = case["patient"]["voice_id"]
        parser, splitter = stream.UtteranceStream(), stream.SentenceSplitter(first_clause=True)
        spoken, dropped_banned, idx = [], [], 0
        marks = {"ttft": None, "first_sentence": None, "tts_first_ms": None, "audio_start": None}
        err = None
        flushed = False

        async def speak(sentence):
            nonlocal idx
            sentence, hits = brain.strip_banned(sentence, case["banned_words"])
            dropped_banned.extend(hits)
            sentence = voice.speakable(sentence, keep_first=not any("..." in x for x in spoken))
            if not sentence or cancel.is_set():
                return
            t = time.monotonic()
            first = await self._first_chunk(loop, sentence, voice_id, speed, voice.instruction(case, voice.labels_so_far(parser.buf)))
            if first is None or cancel.is_set():
                return
            chunks, audio = first
            if marks["audio_start"] is None:
                marks["tts_first_ms"] = ms(t, time.monotonic())
                marks["audio_start"] = time.monotonic()
                # deliberate `slowed` pause, counted from the end of the doctor's speech so it absorbs compute time
                marks["pause_applied"] = max(0.0, timing["t_end"] + pause - marks["audio_start"])
                if marks["pause_applied"]:
                    await asyncio.sleep(marks["pause_applied"])
                    if cancel.is_set():
                        return
                await self.send_json({"type": "speaking", "slowed_pause_ms": round(marks["pause_applied"] * 1000)})
                await self.twin({"event": "patient_start", "turn": self.turn_no})
            pcm = stt.float_to_pcm16(np.asarray(audio, dtype=np.float32))
            await self.send_json({"type": "sentence", "index": idx, "text": sentence, "samples": len(pcm) // 2})
            spoken.append(sentence)
            idx += 1
            while pcm:  # later chunks of a streamed sentence go out as bare PCM, which the client appends to the same sentence
                await self.send_bytes(pcm)
                self.playing_until = max(self.playing_until, time.monotonic()) + len(pcm) / 2 / OUT_SR
                try:
                    audio = await loop.run_in_executor(TTS_POOL, next, chunks, None)
                except Exception as e:  # mid-sentence failure: drop the rest of this sentence, the next one uses the fallback
                    self._tts_failed(e)
                    audio = None
                if audio is None or cancel.is_set():
                    break
                pcm = stt.float_to_pcm16(np.asarray(audio, dtype=np.float32))

        while True:
            kind, val = await q.get()
            if kind == "chunk":
                if marks["ttft"] is None:
                    marks["ttft"] = time.monotonic()
                pieces = splitter.feed(parser.feed(val))
                if parser.done and not flushed:  # the utterance string closed: speak its tail now, not when the whole JSON ends
                    pieces, flushed = pieces + splitter.flush(), True
                for s in pieces:
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
        # intent tagging runs after the voice stream: on one GPU a parallel request halves the patient's token rate
        tagged = await loop.run_in_executor(None, brain.tag_intents, text, prev, self.client, model)
        if was_interrupted:
            tagged = tagged + ["interrupt"]

        meta = {"model": model, "allowed_fact_ids": allowed, "fallback": False, "guard_dropped": []}
        try:
            if err:
                raise RuntimeError(err)
            raw = parser.full()
            jsonschema.validate(raw, brain.loose(schema))
            reply, meta["guard_dropped"] = brain.guard({**raw, "doctor_intents": tagged}, case, state["trust"])
            meta["guard_dropped"] += twin.enforce_discomfort(reply, recalled)
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
        expr = twin.expression(reply, case)
        have = {c["id"] for c in reply["event_cues"]}
        reply["event_cues"] = (reply["event_cues"] + [c for c in expr["cues"] if c["id"] not in have])[:2]
        self.next_speed = expr["speed"]
        self.state, self.mood = twin.update(state, self.mood, reply, case)
        loop.run_in_executor(None, self.warm)
        await self.send_json({"type": "intents", "doctor_intents": tagged})
        await self.send_json({"type": "reply", "turn": self.turn_no, "reply": reply, "state": self.state, "meta": meta})
        await self.twin(twin.snapshot(self.turn_no, text, reply, recalled, self.state, self.mood,
                                      twin.why(recalled, reply, state["trust"], case), self.next_speed))
        await self.twin({"event": "patient_end", "turn": self.turn_no})

        t_end = timing.pop("t_end")
        timing.update({
            "type": "timing", "turn": self.turn_no,
            "llm_ttft_ms": ms(t_llm, marks["ttft"]), "llm_first_sentence_ms": ms(t_llm, marks["first_sentence"]),
            "llm_total_ms": ms(t_llm, t_done), "tts_first_chunk_ms": marks["tts_first_ms"],
            "audio_start_ms": ms(t_end, marks["audio_start"]),  # end of doctor speech -> first patient audio ready, excluding pause
            "slowed_pause_ms": round(marks.get("pause_applied", 0) * 1000),  # extra wait added after audio was ready
            "slowed_target_ms": round(pause * 1000), "banned_dropped": dropped_banned,
        })
        await self.send_json(timing)
        log.info("turn %d timing %s", self.turn_no, json.dumps({k: v for k, v in timing.items() if k.endswith("_ms")}))
        await self.send_json({"type": "listening"})

    async def run_staged_turn(self, text, timing, cancel):
        """Concept-preview turn: the next scripted line and its pre-rendered audio, sent at the planned latency."""
        loop = asyncio.get_running_loop()
        self.turn_no += 1
        self.messages.append({"role": "doctor", "text": text})
        prev = next((m["text"] for m in reversed(self.messages[:-1]) if m["role"] == "patient"), None)
        await self.send_json({"type": "thinking"})
        t, audio = self.staged.next()
        if t is None:
            await self.send_json({"type": "listening"})
            return
        if audio is None:
            audio = await loop.run_in_executor(TTS_POOL, self.tts_fn, t["patient"], self.case["patient"]["voice_id"], 1.0)
        pause = staged.HESITATE_S.get(t.get("nonverbal"), 0.0)
        await asyncio.sleep(max(0.0, timing["t_end"] + staged.GAP_S + pause - time.monotonic()))
        if cancel.is_set():
            return
        t_audio = time.monotonic()
        await self.send_json({"type": "speaking", "slowed_pause_ms": round(pause * 1000)})
        pcm = stt.float_to_pcm16(np.asarray(audio, dtype=np.float32))
        await self.send_json({"type": "sentence", "index": 0, "text": t["patient"], "samples": len(pcm) // 2})
        await self.send_bytes(pcm)
        self.playing_until = max(self.playing_until, time.monotonic()) + len(pcm) / 2 / OUT_SR
        tagged = await loop.run_in_executor(None, brain.tag_intents, text, prev, self.client, brain.default_model())
        reply = {**staged.reply_of(t), "doctor_intents": tagged}
        self.messages.append({"role": "patient", "text": t["patient"]})
        self.state = brain.apply_turn(self.state, reply)
        await self.send_json({"type": "brain_snapshot", "turn": self.turn_no, "brain": t["brain"], "state": self.state, "staged": True})
        await self.send_json({"type": "intents", "doctor_intents": tagged})
        await self.send_json({"type": "reply", "turn": self.turn_no, "reply": reply, "state": self.state,
                              "meta": {"model": "staged", "staged": True, "fallback": False, "guard_dropped": []}})
        t_end = timing.pop("t_end")
        timing.update({"type": "timing", "turn": self.turn_no, "audio_start_ms": ms(t_end, t_audio) - round(pause * 1000),
                       "slowed_pause_ms": round(pause * 1000), "staged": True})
        await self.send_json(timing)
        log.info("staged turn %d timing %s", self.turn_no, json.dumps({k: v for k, v in timing.items() if k.endswith("_ms")}))
        await self.send_json({"type": "listening"})

    async def _first_chunk(self, loop, text, voice_id, speed, instruction):
        """(chunk iterator, first chunk) from the session's TTS backend; if it fails before any audio, the fallback says the sentence."""
        for backend in (self.tts, self.fallback) if self.tts is not self.fallback else (self.fallback,):
            chunks = backend.stream(text, voice_id, speed, instruction)
            try:
                audio = await loop.run_in_executor(TTS_POOL, next, chunks, None)
                return (chunks, audio) if audio is not None else None
            except Exception as e:
                if backend is self.fallback:
                    raise
                self._tts_failed(e)
        return None

    def _tts_failed(self, e):
        if self.tts is not self.fallback:
            log.error("TTS backend failed (%s); KittenTTS for the rest of the session", type(e).__name__)
            self.tts = self.fallback

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
