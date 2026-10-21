"""Turn-taking with fake VAD, Smart Turn and STT: endpoint rule and speculative transcripts. No models loaded."""
import asyncio

import numpy as np

import session
import stt
from test_session import FakeLLM, make


class FakeVad:
    """Replays one event per frame from a script ('s' start, 'e' end after 200 ms of silence, '.' nothing)."""
    def __init__(self, script):
        self.script, self.samples, self.end_sample = list(script), 0, None

    def feed(self, frame):
        self.samples += len(frame)
        ev = self.script.pop(0) if self.script else "."
        if ev == "e":
            self.end_sample = self.samples - 200 * stt.SR // 1000
        return {"s": "start", "e": "end"}.get(ev)

    def reset(self):
        pass


class FakeSmartTurn:
    def __init__(self, *p):
        self.p, self.calls = list(p), 0

    def complete(self, audio):
        self.calls += 1
        return self.p.pop(0)


def run(script, smart, n_frames):
    calls = []

    def fake_stt(audio):
        calls.append(len(audio))
        return f"line {len(calls)}"

    async def go():
        s, ev, _ = make(FakeLLM())
        s.stt_fn = fake_stt
        await s.on_json({"type": "start", "case_id": "mdd_01"})
        s.vad, s.smart_turn = FakeVad(script), smart
        heard_at = None
        for i in range(n_frames):
            await s.on_frame(np.zeros(stt.FRAME, np.float32))
            if heard_at is None and any(m["type"] == "transcript" and m["text"] for _, m in ev):
                heard_at = i
        if s.turn_task:
            await s.turn_task
        return heard_at, [m["text"] for _, m in ev if m["type"] == "transcript" and m["text"]], calls
    return asyncio.run(go())


FRAME_MS = stt.FRAME * 1000 // stt.SR  # 32


def test_complete_turn_ends_at_first_silence():
    heard, texts, calls = run("s" + "." * 20 + "e", FakeSmartTurn(0.9), 60)
    assert heard == 21 and texts == ["line 1"] and len(calls) == 1


def test_unfinished_turn_waits_for_the_hard_cap():
    heard, texts, calls = run("s" + "." * 20 + "e", FakeSmartTurn(0.1), 80)
    cap_frames = -(-(session.TURN_CAP_MS - 200) // FRAME_MS)  # silence already 200 ms at the end event
    assert heard == 21 + cap_frames and texts == ["line 1"]
    assert len(calls) == 1  # the speculative transcript was used, not re-run


def test_resumed_speech_discards_speculative_transcript():
    heard, texts, calls = run("s" + "." * 10 + "e" + "...s" + "." * 10 + "e", FakeSmartTurn(0.1, 0.9), 60)
    assert texts == ["line 2"] and len(calls) == 2 and calls[1] > calls[0]


def test_without_smart_turn_ends_at_the_silence_setting():
    heard, texts, _ = run("s" + "." * 20 + "e", None, 60)
    extra = -(-(stt.SILENCE_MS - 200) // FRAME_MS)
    assert heard == 21 + extra and texts == ["line 1"]
