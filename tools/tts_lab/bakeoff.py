"""TTS bake-off for the patient voice (Phase G). Run with llama-server loaded, as in live use.

  tools/tts_lab/.venv/bin/python tools/tts_lab/bakeoff.py            # mlx-audio candidates
  server/patient-service/.venv/bin/python tools/tts_lab/bakeoff.py --kitten   # KittenTTS mini baseline (service venv)
  server/patient-service/.venv/bin/python tools/tts_lab/bakeoff.py --score    # STT accuracy, emotion separation, report + listening page

Writes WAVs and per-model JSON under tools/tts_lab/bakeoff/ (git-ignored), docs/tts-bakeoff.md and docs/listening/index.html.
Emotion separation = mean |Δ median F0| (semitones) + mean |Δ RMS| (dB) / 3 between a sad and an anxious instruction on the same sentences.
"""
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tools/tts_lab/bakeoff"
SR = 24000
LINES = ["Just tired, doctor. It's been like this for two months now.",
         "I fall asleep okay, but I'm up by four and I just lie there.",
         "I stopped singing. I don't even call my friends anymore.",
         "My manager shouts at me in front of everyone. I feel so stupid.",
         "Some nights I wish I just wouldn't wake up.",
         "No, I would never do anything. My mother, my brother... I couldn't.",
         "Will I have to take tablets? I don't want my parents to know.",
         "Okay. Thank you. It helps to say it to someone."]
EMO_TEXT = ["I don't know what to do anymore.", "It's been really hard at work.", "I keep thinking about it at night.",
            "My family doesn't know any of this."]
DESC = ("A 24-year-old Indian woman from Bengaluru with a soft, natural Indian-English accent. Young, warm but tired voice, "
        "mid-low pitch. Natural and human, not a narrator.")
EMO = {"sad": "Very sad and tearful, voice breaking, slow and quiet.", "anxious": "Anxious and tense, speaking fast and a little loud."}

# name, HF repo, licence, how to call
CANDIDATES = [
    ("kokoro-82m", "mlx-community/Kokoro-82M-bf16", "Apache-2.0", "kokoro"),
    ("qwen3-tts-1.7b-voicedesign", "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16", "Apache-2.0", "qwen_design"),
    ("qwen3-tts-0.6b-customvoice", "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-bf16", "Apache-2.0", "qwen_custom"),
    ("chatterbox-turbo", "mlx-community/chatterbox-turbo-fp16", "MIT (weights) / Apache-2.0 (MLX port)", "chatterbox"),
]
SKIPPED = [("kitten-tts-2", "Stellon Labs Community License: revenue-capped, not MIT/Apache/BSD"),
           ("kyutai pocket-tts", "upstream repo is gated (terms click-through); the ungated mirror is not used")]


def _audio(results) -> np.ndarray:
    return np.concatenate([np.asarray(r.audio, dtype=np.float32).reshape(-1) for r in results])


def mlx_run():
    import mlx.core as mx
    from mlx_audio.tts.utils import load_model
    for name, repo, lic, kind in CANDIDATES:
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        try:
            t = time.perf_counter()
            model = load_model(repo)
            load_s = time.perf_counter() - t
            mx.reset_peak_memory()

            def gen(text, emo=None, stream=False):
                ins = f"{DESC} In this line: {EMO[emo]}" if emo else DESC
                if kind == "kokoro":
                    return model.generate(text=text, voice="af_heart", speed=1.0, lang_code="a", stream=stream)
                if kind == "qwen_design":
                    return model.generate(text=text, instruct=ins, lang_code="english", stream=stream, streaming_interval=0.4)
                if kind == "qwen_custom":
                    return model.generate(text=text, voice="serena", instruct=EMO[emo] if emo else None, lang_code="english",
                                          stream=stream, streaming_interval=0.4)
                return model.generate(text=text, exaggeration={"sad": 0.15, "anxious": 0.85}.get(emo, 0.4), stream=stream,
                                      streaming_interval=0.4)

            _audio(list(gen("Hello, doctor.")))  # warm-up
            ttfa = []
            for text in LINES[:4]:
                t = time.perf_counter()
                next(iter(gen(text, stream=True)))
                ttfa.append((time.perf_counter() - t) * 1000)
            gen_s, audio_s = 0.0, 0.0
            for i, text in enumerate(LINES):
                t = time.perf_counter()
                a = _audio(list(gen(text)))
                gen_s += time.perf_counter() - t
                audio_s += len(a) / SR
                sf.write(d / f"line_{i}.wav", a, SR)
            for emo in EMO:
                for i, text in enumerate(EMO_TEXT):
                    sf.write(d / f"emo_{emo}_{i}.wav", _audio(list(gen(text, emo))), SR)
            res = {"model": name, "repo": repo, "licence": lic, "load_s": round(load_s, 1),
                   "ttfa_ms": round(float(np.median(ttfa))), "rtf": round(gen_s / audio_s, 2),
                   "peak_gb": round(mx.get_peak_memory() / 1e9, 1), "instructable": kind != "kokoro"}
        except Exception as e:  # a candidate that cannot run is a result, not a crash
            res = {"model": name, "repo": repo, "licence": lic, "error": f"{type(e).__name__}: {str(e)[:200]}"}
        (d / "result.json").write_text(json.dumps(res, indent=1))
        print(res, flush=True)
        model = None


def kitten_run():
    sys.path.insert(0, str(ROOT / "server/patient-service"))
    from kittenml import KittenTTS
    d = OUT / "kitten-tts-mini-0.8"
    d.mkdir(parents=True, exist_ok=True)
    t = time.perf_counter()
    m = KittenTTS("KittenML/kitten-tts-mini-0.8")
    load_s = time.perf_counter() - t
    m.generate("Hello, doctor.", voice="Luna", speed=1.0)
    first, gen_s, audio_s = [], 0.0, 0.0
    for i, text in enumerate(LINES):
        t = time.perf_counter()
        a = np.asarray(m.generate(text, voice="Luna", speed=1.0), dtype=np.float32)
        dt = time.perf_counter() - t
        first.append(dt * 1000)
        gen_s, audio_s = gen_s + dt, audio_s + len(a) / SR
        sf.write(d / f"line_{i}.wav", a, SR)
    for emo, sp in (("sad", 0.85), ("anxious", 1.15)):  # speed is its only control
        for i, text in enumerate(EMO_TEXT):
            sf.write(d / f"emo_{emo}_{i}.wav", np.asarray(m.generate(text, voice="Luna", speed=sp), dtype=np.float32), SR)
    res = {"model": "kitten-tts-mini-0.8", "repo": "KittenML/kitten-tts-mini-0.8", "licence": "Apache-2.0", "load_s": round(load_s, 1),
           "ttfa_ms": round(float(np.median(first))), "rtf": round(gen_s / audio_s, 2), "peak_gb": None, "instructable": False,
           "note": "no streaming: TTFA = whole first sentence"}
    (d / "result.json").write_text(json.dumps(res, indent=1))
    print(res)


def f0_rms(path) -> tuple[float, float]:
    import librosa
    a, sr = sf.read(path, dtype="float32")
    f0 = librosa.yin(a, fmin=70, fmax=450, sr=sr)
    voiced = f0[(f0 > 70) & (f0 < 450)]
    rms = 20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-9)
    return float(np.median(voiced)) if len(voiced) else 0.0, float(rms)


def score():
    sys.path.insert(0, str(ROOT / "server/patient-service"))
    sys.path.insert(0, str(ROOT / "tools/tts_lab"))
    from scipy.signal import resample_poly
    import stt
    rows = []
    for d in sorted(p for p in OUT.iterdir() if (p / "result.json").exists()):
        r = json.loads((d / "result.json").read_text())
        if "error" not in r:
            ok = tot = 0
            for i, text in enumerate(LINES):
                a, _ = sf.read(d / f"line_{i}.wav", dtype="float32")
                hyp = stt.transcribe(resample_poly(a, 2, 3).astype(np.float32)).lower()
                ref = [w.strip(".,?!'") for w in text.lower().split()]
                ok += sum(w in hyp for w in ref)
                tot += len(ref)
            r["word_acc"] = round(ok / tot, 3)
            sep = []
            for i in range(len(EMO_TEXT)):
                (fs, rs), (fa, ra) = f0_rms(d / f"emo_sad_{i}.wav"), f0_rms(d / f"emo_anxious_{i}.wav")
                st = abs(12 * np.log2(fa / fs)) if fs and fa else 0.0
                sep.append(st + abs(ra - rs) / 3)
            r["emotion_sep"] = round(float(np.mean(sep)), 2)
        rows.append(r)
    eligible = [r for r in rows if "error" not in r and r["word_acc"] >= 0.93 and r["ttfa_ms"] <= 450 and r["rtf"] <= 0.8]
    winner = max(eligible, key=lambda r: (r["emotion_sep"], -r["ttfa_ms"]), default=None)
    (OUT / "summary.json").write_text(json.dumps({"rows": rows, "winner": winner and winner["model"]}, indent=1))
    write_report(rows, winner)
    write_listening(rows)
    print(json.dumps({"winner": winner and winner["model"]}, indent=1))


def write_report(rows, winner):
    lines = ["# TTS bake-off (Phase G)", "",
             f"Date: {time.strftime('%Y-%m-%d')} · M5 Pro 24 GB, llama-server (Gemma 4 E4B) loaded · script: `tools/tts_lab/bakeoff.py`", "",
             "**Decision rule (fixed before the run):** eligible = licence MIT/Apache/BSD, Parakeet word accuracy ≥ 0.93, "
             "time to first audio ≤ 450 ms (streaming where the model supports it), real-time factor ≤ 0.8. "
             "Among eligible models the largest emotion separation wins; ties go to the lower TTFA. None eligible → keep KittenTTS.", "",
             f"**Winner: {winner['model'] if winner else 'none eligible (KittenTTS kept)'}**", "",
             "| Model | Licence | TTFA ms | RTF | Peak GB | Word acc | Emotion sep | Instructions | Note |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['model']} | {r['licence']} | | | | | | | failed: {r['error'][:80]} |")
        else:
            lines.append(f"| {r['model']} | {r['licence']} | {r['ttfa_ms']} | {r['rtf']} | {r['peak_gb'] or ''} | {r['word_acc']} | "
                         f"{r['emotion_sep']} | {'yes' if r['instructable'] else 'no'} | {r.get('note', '')} |")
    lines += ["", "Skipped: " + "; ".join(f"{n} ({why})" for n, why in SKIPPED) + ".", "",
              "Emotion separation is a proxy (pitch and loudness distance between a sad and an anxious rendering of the same sentence), "
              "not a judgement of how natural the emotion sounds. The owner's blind listening page is `docs/listening/index.html`."]
    (ROOT / "docs/tts-bakeoff.md").write_text("\n".join(lines) + "\n")


def write_listening(rows):
    """A blind A/B page: each line once per model, labels shuffled with a fixed seed; the key is folded at the bottom."""
    out = ROOT / "docs/listening"
    out.mkdir(parents=True, exist_ok=True)
    ok = [r["model"] for r in rows if "error" not in r]
    rnd = random.Random(7)
    items, key = [], []
    for i, text in enumerate(LINES):
        order = ok[:]
        rnd.shuffle(order)
        cells = []
        for j, m in enumerate(order):
            name = f"l{i}_{chr(65 + j)}.wav"
            (out / name).write_bytes((OUT / m / f"line_{i}.wav").read_bytes())
            cells.append(f'<td><b>{chr(65 + j)}</b><br><audio controls preload="none" src="{name}"></audio></td>')
            key.append(f"Line {i + 1} {chr(65 + j)} = {m}")
        items.append(f"<tr><td>{i + 1}. {text}</td>{''.join(cells)}</tr>")
    html = f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Voice listening test</title>
<style>body{{font-family:system-ui;margin:24px;background:#fbfbf8;color:#1c2b2a}}td{{padding:8px;border-bottom:1px solid #ddd;vertical-align:top}}audio{{width:180px}}</style>
<h1>Patient voice: blind listening test</h1><p>For each line, note the letter that sounds most like a real, tired 24-year-old Indian woman. Then open the key.</p>
<table>{''.join(items)}</table><details><summary>Answer key</summary><pre>{chr(10).join(key)}</pre></details>"""
    (out / "index.html").write_text(html)


if __name__ == "__main__":
    {"--kitten": kitten_run, "--score": score}.get(sys.argv[1] if len(sys.argv) > 1 else "", mlx_run)()
