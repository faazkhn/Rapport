"""PsychSim patient service: WS /session (voice loop), /health, /reply (typed + tests), /tts (KittenTTS). Run with ./run.sh."""
import io
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Literal

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import brain
import mock
import session
import stt
import twin_bus
import voice

log = logging.getLogger("patient-service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

VOICES = session.VOICES
SAMPLE_RATE = session.OUT_SR
tts = session.TTS
MOCK = os.environ.get("PSYCHSIM_LLM") == "mock"  # dev/play-mode tests only, never the LLM eval


@asynccontextmanager
async def lifespan(app):
    if os.environ.get("PSYCHSIM_SKIP_TTS") != "1":
        try:
            from kittenml import KittenTTS
            t = time.perf_counter()
            tts["model"] = KittenTTS(session.TTS_MODEL)
            session.synth("Hello, doctor.", "Luna", 1.0)  # first call compiles the ONNX graph
            log.info("TTS loaded in %.1fs", time.perf_counter() - t)
        except Exception as e:  # /reply still works without TTS
            log.error("TTS failed to load: %s", type(e).__name__)
        name = os.environ.get("RAPPORT_TTS", "qwen3-design")
        if name != "kitten":
            try:
                t = time.perf_counter()
                tts["backend"] = await run_in_threadpool(voice.load, name, session.synth)
                await run_in_threadpool(lambda: session.TTS_POOL.submit(lambda: list(tts["backend"].stream("Hello, doctor.", "", 1.0, ""))).result())
                log.info("TTS backend %s loaded in %.1fs", name, time.perf_counter() - t)
            except Exception as e:  # sessions use KittenTTS
                log.error("TTS backend %s failed to load (%s); using KittenTTS", name, type(e).__name__)
    if os.environ.get("PSYCHSIM_SKIP_STT") != "1":
        t = time.perf_counter()
        stt.vad_model()
        await run_in_threadpool(lambda: session.STT_POOL.submit(stt.transcribe, np.zeros(stt.SR, np.float32)).result())
        log.info("VAD + STT (%s) loaded in %.1fs", stt.STT_MODEL, time.perf_counter() - t)
    if not MOCK and os.environ.get("PSYCHSIM_SKIP_WARMUP") != "1":
        t = time.perf_counter()
        n = await run_in_threadpool(brain.tag_intents, "Hello, how are you?")  # warms slot 1 prefix
        log.info("LLM %s warm in %.1fs (intents ok=%s)", brain.default_model(), time.perf_counter() - t, n is not None)
    yield


app = FastAPI(title="PsychSim patient service", lifespan=lifespan)


@app.websocket("/twin/ws")  # declared before the /twin static mount, which would otherwise catch it
async def twin_ws(ws: WebSocket):
    await ws.accept()
    q = twin_bus.subscribe()
    try:
        while True:
            await ws.send_json(await q.get())
    except Exception:  # viewer went away
        pass
    finally:
        twin_bus.unsubscribe(q)


app.mount("/twin", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "twin"), html=True), name="twin")  # Digital Twin


class Msg(BaseModel):
    role: Literal["doctor", "patient"]
    text: str = Field(max_length=4000)


class State(BaseModel):
    trust: float = Field(ge=0, le=100)
    distress: float = Field(ge=0, le=100)
    agitation: float = Field(ge=0, le=100)
    engagement: float = Field(ge=0, le=100)


class ReplyReq(BaseModel):
    case_id: str
    variant: Literal["female", "male"] = "female"
    messages: list[Msg] = Field(min_length=1)
    state: State
    elapsed_min: float | None = None
    model: str | None = None
    reasoning_effort: Literal["low", "medium", "high", "xhigh"] | None = None
    summary: str | None = Field(default=None, max_length=4000)


class TtsReq(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    voice: str = "Bella"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


@app.get("/health")
def health():
    return {"ok": True, "model": "mock" if MOCK else brain.default_model(), "backend": "grok" if brain.use_grok() else "local",
            "mock": MOCK, "tts_loaded": tts["model"] is not None, "stt": stt.STT_MODEL}


@app.post("/reply")
async def reply(req: ReplyReq):
    try:
        brain.load_case(req.case_id, req.variant)
    except (FileNotFoundError, KeyError):
        raise HTTPException(404, f"unknown case_id {req.case_id!r}")
    out = await run_in_threadpool(mock.mock_reply if MOCK else brain.generate_reply, req.model_dump())
    m = out["meta"]
    log.info("reply case=%s model=%s latency_ms=%s fallback=%s dropped=%d",
             req.case_id, m["model"], m["latency_ms"], m["fallback"], len(m["guard_dropped"]))
    return out


@app.post("/tts")
async def speak(req: TtsReq):
    if tts["model"] is None:
        raise HTTPException(503, "TTS model not loaded")
    if req.voice not in VOICES:
        raise HTTPException(422, f"voice must be one of {VOICES}")
    t = time.perf_counter()
    audio = await run_in_threadpool(lambda: session.TTS_POOL.submit(session.synth, req.text, req.voice, req.speed).result())
    buf = io.BytesIO()  # audio stays in memory, never on disk
    sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    ms = round((time.perf_counter() - t) * 1000)
    log.info("tts voice=%s chars=%d gen_ms=%d", req.voice, len(req.text), ms)
    return Response(buf.getvalue(), media_type="audio/wav", headers={"X-Gen-Ms": str(ms)})


@app.websocket("/session")
async def ws_session(ws: WebSocket):
    await session.serve(ws)
