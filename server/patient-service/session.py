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
import exam_router
import learning
import mind
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
INTERRUPT_MIN_S = 1.0  # the doctor cut the patient off only if this much of the reply was still to play (not while thinking, not the last word)
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
        self.asked = None  # exam action waiting for "which hand?" to be answered (one turn)
        self.smart_turn = SMART["model"]
        self.silence_ms = stt.SILENCE_MS
        self.turn_task = None
        self.cancel = threading.Event()
        self.playing_until = 0.0  # monotonic time the client should finish playing what we sent
        self.said_all = False  # this turn's utterance is closed and every sentence went to TTS
        self.interrupted = False
        self.turn_no = 0
        self.staged = None  # staged.Script in RAPPORT_STAGED concept-preview mode
        self.mind = None  # Digital Twin mind for this session (mind.py): mood, memory, resistance, fired events, next speed
        self.twin_log = None  # this session's Twin event log (JSONL)
        self.mode = "practice"  # assessment: only faculty-approved examples
        self.consent = False  # a learner's turns feed learning only with this per-session consent

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
            seed = msg.get("seed")
            if seed is not None and (isinstance(seed, bool) or not (isinstance(seed, int) and 0 <= seed < 2**31)):
                raise KeyError(f"bad seed {seed!r}")
            self.case = brain.load_case(msg["case_id"], msg.get("variant", "female"), seed,
                                        "assessment" if msg.get("mode") == "assessment" else "practice")
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
        self.mode = "assessment" if msg.get("mode") == "assessment" else "practice"
        self.consent = msg.get("learning_consent") is True
        p = self.case["patient"]
        await self.send_json({"type": "session", "case_id": self.case["id"], "variant": self.case["variant"], "name": p["name"],
                              "model_id": p["model_id"], "voice_id": p["voice_id"], "state": self.state,
                              "in_rate": stt.SR, "out_rate": OUT_SR, "llm": brain.default_model(), "staged": staged.enabled(),
                              "style": self.case["style"], "generated": self.case.get("generated")})
        self.mind = mind.new(self.case, self.state)
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
            asyncio.get_running_loop().run_in_executor(TTS_POOL, self.warm_voice, self.tts)
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
        with contextlib.suppress(Exception):  # loads the embedder and the library index off the voice path
            learning.retrieve(self.case["id"], "hello", self.mode, learning.current().get("examples_k", 0))
        if brain.use_grok():
            return
        with contextlib.suppress(Exception):
            msgs = self.messages + [{"role": "doctor", "text": ""}]
            kw = brain.llm_kwargs(brain.default_model(), brain.build_messages(self.case, self.state, msgs), {"type": "object"}, "warm", 0)
            kw.pop("response_format")
            (self.client or brain.get_client()).chat.completions.create(**{**kw, "max_tokens": 1})

    def warm_voice(self, backend):
        """One short line through the session's voice while the patient walks in: after a long idle the TTS weights are paged out
        and the first reply's voice took 10 s."""
        with contextlib.suppress(Exception):
            for _ in backend.stream("Hmm.", self.case["patient"]["voice_id"], 1.0, voice.instruction(self.case, {})):
                pass

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
        # once the utterance is said, the turn is only finishing its JSON (state, facts): talking then is not an interruption
        return (self.turn_task is not None and not self.turn_task.done() and not self.said_all) or time.monotonic() < self.playing_until

    async def barge_in(self):
        cut = self.playing_until - time.monotonic() >= INTERRUPT_MIN_S  # measured when the doctor starts, not when the reply stops
        if brain.cue_live(self.case, "pressured_speech", self.state) > 0.1:
            async def later():  # talks over the doctor briefly; a task so mic frames keep flowing
                await asyncio.sleep(PRESSURED_OVERLAP_S)
                await self.stop("barge_in", cut)
            asyncio.create_task(later())
        else:
            await self.stop("barge_in", cut)

    async def stop(self, reason, cut=None):
        t = time.monotonic()
        self.cancel.set()
        if reason == "barge_in" and (cut if cut is not None else self.playing_until - t >= INTERRUPT_MIN_S):
            self.interrupted = True
        self.playing_until = 0.0
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
        case = self.case
        self.turn_no += 1
        self.said_all = False
        self.mind["interrupted"], self.interrupted = self.interrupted, False  # the doctor talked over the previous reply
        elapsed = (time.monotonic() - self.t_start) / 60
        self.messages.append({"role": "doctor", "text": text})
        prev = next((m["text"] for m in reversed(self.messages[:-1]) if m["role"] == "patient"), None)
        earlier = [m["text"] for m in self.messages if m["role"] == "patient"]
        model = brain.default_model()
        await self.twin({"event": "doctor_end", "turn": self.turn_no})
        # one Digital Twin pipeline for the voice and typed paths (mind.py): exam, events, rubric, recall, memory, prompt
        turn = mind.prepare(case, self.state, self.mind, self.messages, elapsed, self.mode)
        exam, events, state = turn["exam"], turn["events"], turn["state"]
        if exam and (exam["actions"] or exam["relax"]):  # before the LLM, so the body moves while the patient thinks
            await self.send_json({"type": "exam", "turn": self.turn_no, "actions": exam["actions"], "relax": exam["relax"]})
        await self.send_json({"type": "thinking"})
        if events:  # code decides when a ward event happens; the model only plays it
            acts = [{"id": e["action"], "comply": True} for e in events if e.get("action")]
            if acts:
                await self.send_json({"type": "exam", "turn": self.turn_no, "actions": acts, "relax": False})
            for e in events:
                await self.twin({"event": "ward_event", "turn": self.turn_no, "id": e["id"], "say": e["say"]})
        schema = turn["schema"]
        kw = brain.llm_kwargs(model, turn["messages"], schema, "patient_reply", 0)
        q: asyncio.Queue = asyncio.Queue()
        t_llm = time.monotonic()
        loop.run_in_executor(None, self._llm_stream, kw, q, loop, cancel)

        pause = brain.slowed_pause_s(case, state)
        speed = tts_speed(case, state) * self.mind["next_speed"]
        voice_id = case["patient"]["voice_id"]
        parser, splitter = stream.UtteranceStream(), stream.SentenceSplitter(first_clause=True)
        spoken, dropped_banned, held, idx = [], [], [], 0
        word_cap, capped = brain.style(case)["word_cap"], False
        marks = {"ttft": None, "first_sentence": None, "tts_first_ms": None, "audio_start": None}
        err = None
        flushed = False

        async def speak(sentence, checked=False):
            nonlocal idx, capped
            if not checked:
                sentence, hits = mind.speakable(case, turn, sentence, spoken, earlier)
                dropped_banned.extend(hits)
                if sentence and (held or mind.hold(turn, sentence, spoken)):  # a possible flat denial waits for the rest of the reply
                    held.append(sentence)
                    return
            sentence = voice.speakable(sentence, keep_first=not any("..." in x for x in spoken))
            if not sentence or cancel.is_set():
                return
            if capped or spoken and sum(len(x.split()) for x in spoken) + len(sentence.split()) > word_cap:  # style word cap, as brain.cap_words
                capped = True
                return
            t = time.monotonic()
            first = await self._first_chunk(loop, sentence, voice_id, speed, voice.instruction(case, voice.labels_so_far(parser.buf)))
            if first is None or cancel.is_set():
                return
            chunks, audio = first
            pcm = stt.float_to_pcm16(np.asarray(audio, dtype=np.float32))
            while not voice.ready_to_play(sentence, len(pcm) / 2 / OUT_SR, time.monotonic() - t, self.playing_until - time.monotonic()):
                try:
                    audio = await loop.run_in_executor(TTS_POOL, next, chunks, None)
                except Exception as e:  # mid-sentence failure: say what was made, the next sentence uses the fallback
                    self._tts_failed(e)
                    audio = None
                if audio is None or cancel.is_set():
                    chunks = iter(())
                    break
                pcm += stt.float_to_pcm16(np.asarray(audio, dtype=np.float32))
            if cancel.is_set():
                return
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

        async def release_held():
            """The reply is complete: a held flat denial is replaced if it breaks a rule, else said as it was."""
            if not held:
                return
            lines, held[:] = list(held), []
            fix = mind.final_check(turn, " ".join(lines))
            for s in ([fix] if fix else lines):
                await speak(s, checked=True)

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
                if flushed:
                    await release_held()
                self.said_all = flushed and not cancel.is_set()
            elif kind == "error":
                err = val
                break
            else:
                break
        if not cancel.is_set():
            for s in splitter.flush():
                marks["first_sentence"] = marks["first_sentence"] or time.monotonic()
                await speak(s)
            await release_held()
        if spoken and turn["ctx"] and turn["plan"] and turn["plan"].get("must_disclose") and not any(c["kind"] in ("denied_open_risk", "risk_not_disclosed") for c in turn["clashes"]):
            mind.final_check(turn, " ".join(spoken))  # logs a reply that dodged an open, kindly asked risk fact
        t_done = time.monotonic()
        # intent tagging runs after the voice stream: on one GPU a parallel request halves the patient's token rate
        tagged = await loop.run_in_executor(None, brain.tag_intents, text, prev, self.client, model)
        if self.mind.get("interrupted"):
            tagged = tagged + ["interrupt"]

        meta = {"model": model, "allowed_fact_ids": turn["allowed"], "fallback": False, "guard_dropped": [],
                "brain_version": learning.brain_version(turn["version"])}
        try:
            if err:
                raise RuntimeError(err)
            raw = parser.full()
            jsonschema.validate(raw, brain.loose(schema))
            reply, meta["guard_dropped"] = mind.guard_reply(case, turn, raw, tagged)
        except Exception as e:
            meta.update(fallback=True, errors=[type(e).__name__])
            reply = {**brain.fallback_reply(case), "doctor_intents": tagged}
            if not spoken and not cancel.is_set():
                await speak(reply["utterance"], checked=True)
        reply["exam_action"] = brain.first_complied(exam)
        if capped:  # facts in the unspoken tail are not credited
            meta["guard_dropped"] += [{"kind": "fact", "id": i, "reason": "word_cap"} for i in reply["revealed_fact_ids"]]
            reply["revealed_fact_ids"] = []
        reply["utterance"] = " ".join(spoken) if spoken else ("" if events else reply["utterance"])
        if cancel.is_set():
            meta["barge_in"] = True
            reply["utterance"] = (" ".join(spoken) + "...") if spoken else ""
        if turn["clashes"]:
            meta["consistency"] = turn["clashes"]
        if turn["plan"]:
            meta["decision"] = {k: turn["plan"][k] for k in ("moves", "resistance_level", "behaviours", "reactions", "must_disclose")}
        if reply["utterance"]:
            self.messages.append({"role": "patient", "text": reply["utterance"]})
        # the event never reached the doctor (nothing said): it may fire again and its nudge is undone
        self.state = mind.finish(case, self.mind, turn, reply, spoken_ok=bool(spoken) or not events)
        loop.run_in_executor(None, self.warm)
        await self.send_json({"type": "intents", "doctor_intents": tagged})
        await self.send_json({"type": "reply", "turn": self.turn_no, "reply": reply, "state": self.state, "meta": meta})
        await self.twin(mind.snapshot(case, self.mind, turn, reply, self.state))
        if turn["clashes"]:
            await self.twin({"event": "consistency", "turn": self.turn_no, "clashes": turn["clashes"]})
        await self.twin({"event": "patient_end", "turn": self.turn_no})
        if self.mind["ended"] and any(e["id"] == "patient_ends" for e in events):
            await self.send_json({"type": "patient_ended", "turn": self.turn_no})
        if self.consent and not cancel.is_set():
            history = [m["text"] for m in self.messages[:-1] if m["role"] == "patient"]
            if not learning.gate(reply["utterance"], meta, case, state, history):
                with contextlib.suppress(OSError):  # learning never stops the voice
                    learning.add_experience(case["id"], {"doctor": text, "utterance": reply["utterance"], "engagement": state["engagement"],
                                                         "trust": state["trust"], "behaviour": reply["behaviour"], "source": "live"},
                                            consent=True)

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
        relax = exam_router.route(t["doctor"])["relax"]  # scripted lines drive the body too ("you can put them down")
        if t.get("exam_action") or relax:
            acts = [{"id": t["exam_action"], "slots": {}, "comply": True}] if t.get("exam_action") else []
            await self.send_json({"type": "exam", "turn": self.turn_no, "actions": acts, "relax": relax})
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
