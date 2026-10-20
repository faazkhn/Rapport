"""Render the staged-demo patient lines (demo/staged/script.json) with Qwen3-TTS VoiceDesign via mlx-audio.

Voices are designed from text only (no reference recordings). Each line: instruct = patient description + the
line's `voice` field (+ nonverbal hint). Every WAV is transcribed back with the patient service's Parakeet STT;
lines under MIN_ACC word accuracy are re-rendered with the next seed (max 3 tries).

Usage: tools/tts_lab/.venv/bin/python tools/tts_lab/render_staged.py [--only female_3 male_0 ...]
"""
import argparse, json, re, subprocess, sys, time
from pathlib import Path

import mlx.core as mx
import numpy as np
import soundfile as sf
from mlx_audio.tts.utils import load_model

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "demo/staged/script.json"
OUT = ROOT / "demo/staged/audio"
MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16"
SERVICE_PY = ROOT / "server/patient-service/.venv/bin/python"
SR = 24000
MIN_ACC = 0.9
TRIES = 3

VOICES = {
    "female": dict(key="turns", seed=1234, desc=(
        "A 24-year-old Indian woman from Bengaluru with a soft, natural Indian-English accent. "
        "Young, warm but tired voice, mid-low pitch, speaking quietly and slowly, like someone who is depressed "
        "and exhausted. Natural and human, not a narrator.")),
    "male": dict(key="arjun_turns", seed=4321, desc=(
        "A 24-year-old Indian man from Bengaluru with a natural Indian-English accent. "
        "Young, low and soft male voice, tired and heavy, speaking quietly and slowly, like someone who is "
        "depressed and exhausted. Natural and human, not a narrator.")),
}
NONVERBAL = {
    "sigh": "Begin with a small audible sigh.",
    "sniff": "A small sniff, voice wet with held-back tears.",
    "breath": "A soft breath before speaking.",
    "shaky_breath": "Begin with a shaky, trembling breath.",
    "exhale": "A soft relieved exhale.",
}
# Seed offsets picked by the STT retry loop on the last full render (attempt index per file); default 0.
SEED_OFFSETS = {}

STT_SNIPPET = """
import sys, json, numpy as np, soundfile as sf
from scipy.signal import resample_poly
sys.path.insert(0, %r)
import stt
for p in sys.argv[1:]:
    a, sr = sf.read(p, dtype='float32')
    a = resample_poly(a, 2, 3).astype(np.float32) if sr == 24000 else a
    print(json.dumps({'path': p, 'text': stt.transcribe(a)}), flush=True)
""" % str(ROOT / "server/patient-service")


def words(s):
    return re.findall(r"[a-z0-9']+", s.lower().replace("practised", "practiced"))


def word_acc(ref, hyp):
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))  # word-level Levenshtein
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
    return max(0.0, 1 - d[len(h)] / max(1, len(r)))


def transcribe(paths):
    out = subprocess.run([str(SERVICE_PY), "-c", STT_SNIPPET, *map(str, paths)], capture_output=True, text=True)
    if out.returncode:
        sys.exit(out.stderr[-2000:])
    return {json.loads(l)["path"]: json.loads(l)["text"] for l in out.stdout.splitlines() if l.startswith("{")}


def tidy(a):
    """Trim silence (lead <= 60 ms, trail <= 120 ms) and peak-normalise to -3 dBFS."""
    a = a.astype(np.float32) - float(np.mean(a))
    hop = SR // 100
    rms = np.sqrt(np.convolve(a ** 2, np.ones(hop) / hop, "same"))
    on = np.flatnonzero(rms > np.max(rms) * 10 ** (-40 / 20))  # -40 dB below loudest 10 ms
    a = a[max(0, on[0] - int(0.06 * SR)): on[-1] + int(0.12 * SR)]
    fade = int(0.005 * SR)
    a[:fade] *= np.linspace(0, 1, fade); a[-fade:] *= np.linspace(1, 0, fade)
    return a * (10 ** (-3 / 20) / np.max(np.abs(a)))


def render(model, desc, turn, seed, stats):
    instruct = f"{desc} In this line: {turn['voice']}. {NONVERBAL.get(turn['nonverbal'] or '', '')}".strip()
    mx.random.seed(seed)
    t = time.perf_counter()
    res = list(model.generate_voice_design(text=turn["patient"], instruct=instruct, language="English"))
    audio = np.concatenate([np.array(r.audio) for r in res])
    stats.append(dict(gen_s=time.perf_counter() - t, audio_s=len(audio) / SR,
                      peak_mem_gb=max(r.peak_memory_usage for r in res)))
    return tidy(audio)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    script = json.loads(SCRIPT.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(f"{g}_{i}", v, t) for g, v in VOICES.items() for i, t in enumerate(script[v["key"]])]
    jobs = [j for j in jobs if not args.only or j[0] in args.only]

    t = time.perf_counter()
    model = load_model(MODEL)
    print(f"load {time.perf_counter() - t:.1f}s")
    stats, report = [], {}
    pending = {name: SEED_OFFSETS.get(name, 0) for name, _, _ in jobs}
    for attempt in range(TRIES):
        for name, v, turn in jobs:
            if name in pending:
                seed = v["seed"] + 1000 * jobs.index((name, v, turn)) + pending[name]
                sf.write(OUT / f"{name}.wav", render(model, v["desc"], turn, seed, stats), SR, subtype="PCM_16")
        texts = transcribe([OUT / f"{n}.wav" for n in pending])
        for name, v, turn in jobs:
            if name not in pending:
                continue
            hyp = texts[str(OUT / f"{name}.wav")]
            acc = word_acc(turn["patient"], hyp)
            report[name] = dict(acc=round(acc, 3), hyp=hyp, seed_offset=pending[name], tries=attempt + 1)
            print(f"{name} try{attempt + 1} acc={acc:.2f} | {hyp}")
        pending = {n: o + 1 for n, o in pending.items() if report[n]["acc"] < MIN_ACC}
        if not pending:
            break

    for name, _, _ in jobs:
        a, _ = sf.read(OUT / f"{name}.wav")
        report[name].update(dur_s=round(len(a) / SR, 2), peak_dbfs=round(20 * np.log10(np.max(np.abs(a))), 2),
                            rms_dbfs=round(20 * np.log10(np.sqrt(np.mean(a ** 2))), 1))
    gen, dur = sum(s["gen_s"] for s in stats), sum(s["audio_s"] for s in stats)
    report["_perf"] = dict(rtf=round(gen / dur, 3), peak_mem_gb=round(max(s["peak_mem_gb"] for s in stats), 2),
                           renders=len(stats))
    rp = Path(__file__).with_name("report.json")
    old = json.loads(rp.read_text()) if rp.exists() else {}
    rp.write_text(json.dumps({**old, **report}, indent=1))
    print(json.dumps(report["_perf"]))


if __name__ == "__main__":
    main()
