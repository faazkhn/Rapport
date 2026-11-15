"""Render the showcase film's doctor lines in the owner's cloned voice (Qwen3-TTS 1.7B Base voice cloning via mlx-audio).

  ~/Downloads/TunnelVerse-CII/.venv/bin/python tools/tts_lab/render_doctor_clone.py [script.json] [line indices...]

Reads turns[i].doctor from demo/staged/showcase/script.json, writes <script dir>/doctor/female_<i>.wav (48 kHz mono) and
report.json. Each line gets up to 8 takes scored like the CII film (Whisper transcript match, speaker similarity, pitch sanity,
pitch movement); exits 1 if any line's transcript match is below 0.9. Unchanged lines are reused.
Reference: the owner's 2026-11-03 recording, ~/Downloads/modern-apartment/Video/cii-final/voice/reference-faaz.wav.
"""
import difflib
import json
import re
import subprocess
import sys
import zlib
from pathlib import Path

import mlx.core as mx
import mlx_whisper
import numpy as np
import soundfile as sf
from mlx_audio.tts.utils import load_model
from num2words import num2words

ROOT = Path(__file__).resolve().parents[2]
REF = Path.home() / "Downloads/modern-apartment/Video/cii-final/voice/reference-faaz.wav"
REF_TEXT = ("Hi, I'm Faaz, and I'm building Prevista. Imagine walking through your next home, before you ever visit it. You can "
            "change the walls, switch on the lights, and see how every room connects. That's exactly what we are building, and "
            "honestly? It's incredibly exciting.")
ASR = "mlx-community/whisper-large-v3-turbo"
TAKES = 4


def words(t):
    t = re.sub(r"\d+", lambda m: " " + num2words(int(m.group())) + " ", t.lower())
    return re.sub(r"[^a-z ]", " ", t.replace("-", " ")).split()


def f0_track(a, sr):
    # YIN (plain autocorrelation jumps an octave on bright voices); returns median f0 and movement in semitones
    hop, n, lo, hi = int(sr * .01), int(sr * .05), int(sr / 400), int(sr / 60)
    out = []
    for i in range(0, len(a) - n - hi, hop):
        x = a[i:i + n]
        if np.sqrt((x ** 2).mean()) < .015:
            continue
        d = np.array([np.sum((x[:n - hi] - x[t:t + n - hi]) ** 2) for t in range(hi)])
        cm = d[1:] * np.arange(1, hi) / (np.cumsum(d[1:]) + 1e-9)
        cand = np.flatnonzero(cm[lo:] < .15)
        if len(cand):
            out.append(sr / (lo + cand[0] + 1))
    f = np.array(out)
    return (float(np.median(f)), float(np.std(12 * np.log2(f)))) if len(f) > 20 else (0.0, 0.0)


def main():
    args = sys.argv[1:]
    script_path = Path(args.pop(0)) if args and args[0].endswith(".json") else ROOT / "demo/staged/showcase/script.json"
    only = {int(a) for a in args}
    turns = json.loads(script_path.read_text())["turns"]
    out = script_path.parent / "doctor"
    out.mkdir(exist_ok=True)
    report_path = out / "report.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {"lines": {}}

    base = load_model("mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit")
    emb = lambda a: (lambda e: e / np.linalg.norm(e))(np.array(base.extract_speaker_embedding(mx.array(a))).ravel())
    ref_a, ref_sr = sf.read(REF, dtype="float32")
    ref_e, (ref_f0, _) = emb(ref_a), f0_track(ref_a, ref_sr)

    for i, turn in enumerate(turns):
        say, dst, key = turn["doctor"], out / f"female_{i}.wav", str(i)
        if i not in only and report["lines"].get(key, {}).get("text") == say and dst.exists():
            continue
        takes = []
        for take in range(2 * TAKES):
            mx.random.seed(zlib.crc32(f"doctor:{take}:{say}".encode()))
            res = list(base.generate(text=say, ref_audio=str(REF), ref_text=REF_TEXT, lang_code="english"))
            a, sr = np.concatenate([np.array(r.audio) for r in res]).astype(np.float32), res[0].sample_rate
            tmp = out / f"take-{take}.wav"
            sf.write(tmp, a, sr)
            heard = mlx_whisper.transcribe(str(tmp), path_or_hf_repo=ASR, language="en")["text"].strip()
            match = difflib.SequenceMatcher(None, words(say), words(heard)).ratio()
            f0, sd = f0_track(a, sr)
            sim = float(emb(a) @ ref_e)
            wps = len(say.split()) / (len(a) / sr)
            sane = 2.0 <= wps <= 4.2 and ref_f0 > 0 and abs(f0 - ref_f0) / ref_f0 < .2
            score = (match >= .93) * 10 + sane * 5 + match * 4 + sim * 4 + sd * .5
            takes.append((score, take, match, sim, sd, f0, wps, heard))
            print(f"  [{i}] take {take}: text {match:.2f} sim {sim:.3f} move {sd:.2f}st f0 {f0:.0f} {wps:.1f}w/s")
            if (match >= .98 and sane and take >= 2) or (take >= TAKES - 1 and max(takes)[0] >= 15):
                break  # 15+ means a clean transcript at the owner's pitch and pace
        score, take, match, sim, sd, f0, wps, heard = max(takes)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out / f"take-{take}.wav"), "-ar", "48000", "-ac", "1", str(dst)], check=True)
        report["lines"][key] = {"text": say, "heard": heard, "text_match": round(match, 3), "speaker_similarity": round(sim, 4),
                                "pitch_movement_st": round(sd, 2), "f0": round(f0), "words_per_sec": round(wps, 2)}
        print(f"{i}: take {take}: {heard}")
        report_path.write_text(json.dumps(report, indent=1))
    for p in out.glob("take-*.wav"):
        p.unlink()
    low = [k for k, v in report["lines"].items() if v["text_match"] < .9]
    print(f"done; {len(report['lines'])} lines, below 0.9: {low}")
    sys.exit(1 if low else 0)


if __name__ == "__main__":
    main()
