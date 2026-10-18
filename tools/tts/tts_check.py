"""Smoke test for KittenTTS on this Mac: loads a model, speaks sample patient lines, reports speed.

Usage: .venv/bin/python tts_check.py [model_id]
"""
import sys, time, pathlib
import soundfile as sf
from kittenml import KittenTTS

MODEL = sys.argv[1] if len(sys.argv) > 1 else "KittenML/kitten-tts-mini-0.8"
OUT = pathlib.Path(__file__).parent / "samples"
OUT.mkdir(exist_ok=True)

# (voice, speed, line): speed stands in for the cue system (slowed < 1 < pressured_speech)
LINES = [
    ("Bruno", 0.85, "I don't know, doc. I just... haven't felt like doing anything for a while."),
    ("Jasper", 1.0, "Look, I like a drink like anyone else. Maybe more than I should."),
    ("Luna", 1.0, "Is this going to be on my record? I don't want my parents finding out."),
    ("Hugo", 1.3, "I've got so many ideas right now, I haven't slept, I don't need to, honestly I feel amazing!"),
]

t0 = time.perf_counter()
m = KittenTTS(MODEL)
print(f"model {MODEL} loaded in {time.perf_counter() - t0:.1f}s; voices: {m.available_voices}")

for i, (voice, speed, text) in enumerate(LINES):
    t = time.perf_counter()
    audio = m.generate(text, voice=voice, speed=speed)
    gen = time.perf_counter() - t
    dur = len(audio) / 24000
    assert dur > 0.5, f"line {i} produced almost no audio"
    path = OUT / f"{MODEL.split('/')[-1]}_{i}_{voice}.wav"
    sf.write(path, audio, 24000)
    print(f"{voice:7} speed {speed}: {gen:.2f}s to make {dur:.1f}s of audio (RTF {gen / dur:.2f}) -> {path.name}")
