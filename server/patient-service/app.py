"""PsychSim patient service: WS /session (voice loop), /health, /reply (typed + tests), /tts (KittenTTS). Run with ./run.sh."""
import io
import ipaddress
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Literal

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException, Query, WebSocket
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.websockets import WebSocketClose

import brain
import examiner
import learning
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
MOCK = brain.env("LLM") == "mock"  # dev/play-mode tests only, never the LLM eval


@asynccontextmanager
async def lifespan(app):
    if brain.env("SKIP_TTS") != "1":
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
    if brain.env("SKIP_STT") != "1":
        t = time.perf_counter()
        stt.vad_model()
        await run_in_threadpool(lambda: session.STT_POOL.submit(stt.transcribe, np.zeros(stt.SR, np.float32)).result())
        log.info("VAD + STT (%s) loaded in %.1fs", stt.STT_MODEL, time.perf_counter() - t)
        try:
            session.SMART["model"] = await run_in_threadpool(stt.smart_turn)
            log.info("Smart Turn %s", "loaded" if session.SMART["model"] else f"missing ({stt.SMART_TURN_ONNX}); silence-only endpointing")
        except Exception as e:
            log.error("Smart Turn failed to load (%s); silence-only endpointing", type(e).__name__)
    if not MOCK and brain.env("SKIP_WARMUP") != "1":
        t = time.perf_counter()
        n = await run_in_threadpool(brain.tag_intents, "Hello, how are you?")  # warms slot 1 prefix
        log.info("LLM %s warm in %.1fs (intents ok=%s)", brain.default_model(), time.perf_counter() - t, n is not None)
    yield


app = FastAPI(title="Rapport patient service", lifespan=lifespan)
LAN_OK = ("/twin", "/health")  # what another device on the network may open; the voice session, replies and learning stay on this Mac


def _loopback(scope) -> bool:
    try:
        return ipaddress.ip_address((scope.get("client") or ("",))[0]).is_loopback
    except ValueError:
        return False


class LocalOnly:
    """run.sh binds every interface so a second laptop on the same Wi-Fi can open the Twin view; nothing else answers it."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket") and not scope["path"].startswith(LAN_OK) and not _loopback(scope):
            deny = PlainTextResponse("Only the Digital Twin view (/twin/) is shared on the network.", 403) if scope["type"] == "http" \
                else WebSocketClose(1008)
            return await deny(scope, receive, send)
        await self.app(scope, receive, send)


app.add_middleware(LocalOnly)


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
    mode: Literal["practice", "assessment"] = "practice"
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)


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


@app.get("/patient")
def patient(case_id: str, variant: Literal["female", "male"] = "female", seed: int | None = Query(default=None, ge=0, le=2**31 - 1),
            mode: Literal["practice", "assessment"] = "practice"):
    """Who the doctor will meet, before the session starts (the prebrief needs it): name, style and the slot values a seed picked.
    The client fills its own copy of the case's {slot} placeholders with `slots`."""
    try:
        c = brain.load_case(case_id, variant, seed, mode)
    except (FileNotFoundError, KeyError):
        raise HTTPException(404, f"unknown case_id {case_id!r}")
    g = c.get("generated", {})
    return {"case_id": c["id"], "variant": c["variant"], "name": c["patient"]["name"], "style": c["style"],
            "style_label": brain.style(c)["label"], "seed": seed, "generator_version": brain.GENERATOR_VERSION,
            "slots": {k: v for o in g.get("slots", {}).values() for k, v in o.items()}, "state_start": c["state_start"]}


class FeedbackReq(BaseModel):
    case_id: str
    variant: Literal["female", "male"] = "female"
    doctor: str = Field(max_length=4000)
    utterance: str = Field(min_length=1, max_length=4000)
    rating: Literal["up", "down", "rewrite"]
    rewrite: str | None = Field(default=None, max_length=4000)
    comment: str | None = Field(default=None, max_length=2000)
    author: str = Field(min_length=1, max_length=100)
    engagement: float = Field(default=35, ge=0, le=100)
    trust: float = Field(default=30, ge=0, le=100)


class ApproveReq(BaseModel):
    case_id: str
    entry_id: str = Field(max_length=64)


def _case_or_404(case_id: str, variant: str = "female"):
    try:
        return brain.load_case(case_id, variant)
    except (FileNotFoundError, KeyError):
        raise HTTPException(404, f"unknown case_id {case_id!r}")


@app.post("/learning/feedback")
async def feedback(req: FeedbackReq):
    """L2 faculty tuning: 👍 / 👎 / rewrite → a principle in the case; 👍 also stores the line as an approved example (L1)."""
    _case_or_404(req.case_id, req.variant)
    text = await run_in_threadpool(learning.distill_principle, req.doctor, req.utterance, req.rating, req.rewrite, req.comment,
                                   brain.get_client())
    principle = learning.add_principle(req.case_id, text, req.author)
    entry = None
    if req.rating == "up":
        entry = learning.add_experience(req.case_id, {"doctor": req.doctor, "utterance": req.utterance, "engagement": req.engagement,
                                                      "trust": req.trust, "behaviour": None, "source": "faculty", "tier": "approved",
                                                      "judged": True, "author": req.author}, consent=False)
    return {"principle": principle, "entry_id": entry and entry["id"]}


@app.post("/learning/approve")
def approve(req: ApproveReq):
    _case_or_404(req.case_id)
    if not learning.approve(req.case_id, req.entry_id):
        raise HTTPException(404, f"unknown entry {req.entry_id!r}")
    return {"ok": True}


class Turn(BaseModel):
    doctor: str = Field(max_length=4000)
    patient: str | None = Field(default=None, max_length=4000)


class AssessReq(BaseModel):
    case_id: str
    variant: Literal["female", "male"] = "female"
    turns: list[Turn] = Field(min_length=1, max_length=200)


@app.post("/assess")
async def assess(req: AssessReq):
    """Debrief: formative AI examiner notes on the doctor's verbal skills, every quote checked against the transcript (examiner.py)."""
    case = _case_or_404(req.case_id, req.variant)
    if MOCK:
        return {"strengths": [], "improvements": [], "dropped_ungrounded": 0, "model": "mock"}
    try:
        out = await run_in_threadpool(examiner.assess, case, [t.model_dump() for t in req.turns])
    except Exception as e:  # the debrief stands without it
        raise HTTPException(503, f"examiner unavailable ({type(e).__name__})")
    log.info("assess case=%s turns=%d notes=%d dropped=%d", req.case_id, len(req.turns), len(out["strengths"]) + len(out["improvements"]), out["dropped_ungrounded"])
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
