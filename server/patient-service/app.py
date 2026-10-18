"""PsychSim patient service: /health, /reply (Grok), /tts (KittenTTS). Run with ./run.sh."""
import contextlib
import io
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Literal

import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, Field

import brain
import mock

log = logging.getLogger("patient-service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TTS_MODEL = "KittenML/kitten-tts-mini-0.8"
VOICES = ["Bella", "Luna", "Rosie", "Kiki", "Jasper", "Bruno", "Hugo", "Leo"]
SAMPLE_RATE = 24000
tts = {"model": None}
MOCK = os.environ.get("PSYCHSIM_LLM") == "mock"  # dev/play-mode tests only, never the LLM eval


@asynccontextmanager
async def lifespan(app):
    if os.environ.get("PSYCHSIM_SKIP_TTS") != "1":
        try:
            from kittenml import KittenTTS
            t = time.perf_counter()
            tts["model"] = KittenTTS(TTS_MODEL)
            log.info("TTS loaded in %.1fs", time.perf_counter() - t)
        except Exception as e:  # /reply still works without TTS
            log.error("TTS failed to load: %s", type(e).__name__)
    yield


app = FastAPI(title="PsychSim patient service", lifespan=lifespan)


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
    return {"ok": True, "model": "mock" if MOCK else brain.DEFAULT_MODEL, "mock": MOCK, "tts_loaded": tts["model"] is not None}


@app.post("/reply")
async def reply(req: ReplyReq):
    try:
        brain.load_case(req.case_id)
    except FileNotFoundError:
        raise HTTPException(404, f"unknown case_id {req.case_id!r}")
    out = await run_in_threadpool(mock.mock_reply if MOCK else brain.generate_reply, req.model_dump())
    m = out["meta"]
    log.info("reply case=%s model=%s latency_ms=%s fallback=%s dropped=%d",
             req.case_id, m["model"], m["latency_ms"], m["fallback"], len(m["guard_dropped"]))
    return out


def _generate(text, voice, speed):
    # kittenml prints the input text to stdout; keep learner/patient text out of logs.
    # shortcut: redirect_stdout is process-wide, so concurrent prints are swallowed too; fine for one client.
    with contextlib.redirect_stdout(io.StringIO()):
        return tts["model"].generate(text, voice=voice, speed=speed)


@app.post("/tts")
async def speak(req: TtsReq):
    if tts["model"] is None:
        raise HTTPException(503, "TTS model not loaded")
    if req.voice not in VOICES:
        raise HTTPException(422, f"voice must be one of {VOICES}")
    t = time.perf_counter()
    audio = await run_in_threadpool(_generate, req.text, req.voice, req.speed)
    buf = io.BytesIO()  # audio stays in memory, never on disk
    sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    ms = round((time.perf_counter() - t) * 1000)
    log.info("tts voice=%s chars=%d gen_ms=%d", req.voice, len(req.text), ms)
    return Response(buf.getvalue(), media_type="audio/wav", headers={"X-Gen-Ms": str(ms)})
