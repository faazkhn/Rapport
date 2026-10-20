"""Staged concept-preview mode (RAPPORT_STAGED=<script.json>): the doctor's audio still goes through the real mic path and VAD, but
each turn replies with the next pre-written patient line and its pre-rendered WAV (demo/staged/audio/<variant>_<i>.wav, falling back
to the live TTS when the file is missing). For presenting planned behaviour only; never used for evaluation or learning.
"""
import json
import os
from pathlib import Path

import numpy as np
import soundfile as sf

PATH = os.environ.get("RAPPORT_STAGED", "")
GAP_S = float(os.environ.get("RAPPORT_STAGED_GAP_S", "0.6"))  # doctor stops -> patient audio, the planned target
HESITATE_S = {"shaky_breath": 1.3}  # clinically sized hesitation for the hardest disclosure; logged as the slowed pause


def enabled() -> bool:
    return bool(PATH)


class Script:
    def __init__(self, variant: str, out_sr: int):
        d = json.loads(Path(PATH).read_text())
        self.turns = d["arjun_turns" if variant == "male" else "turns"]
        self.audio_dir = Path(PATH).parent / "audio"
        self.prefix, self.out_sr, self.i = variant, out_sr, 0

    def next(self):
        """(turn dict, float32 audio or None) for the next line; None when the script is exhausted."""
        if self.i >= len(self.turns):
            return None, None
        t, wav = self.turns[self.i], self.audio_dir / f"{self.prefix}_{self.i}.wav"
        self.i += 1
        if not wav.exists():
            return t, None
        audio, sr = sf.read(wav, dtype="float32", always_2d=True)
        audio = audio.mean(axis=1)
        if sr != self.out_sr:
            x = np.arange(0, len(audio), sr / self.out_sr)
            audio = np.interp(x, np.arange(len(audio)), audio).astype(np.float32)
        return t, audio

    def doctor_line(self) -> str:
        return self.turns[self.i]["doctor"] if self.i < len(self.turns) else ""


def reply_of(t: dict) -> dict:
    return {"emotion": t["emotion"], "utterance": t["patient"], "state_delta": t["state_delta"], "event_cues": t["cues"],
            "revealed_fact_ids": t["facts"], "exam_action": t["exam_action"]}
