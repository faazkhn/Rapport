"""STT accent benchmark (tester brief 2.3b), SYNTHETIC PROXY: learner questions spoken by the macOS en_IN voices.

Real Indian-accented speech sets on Hugging Face (ai4bharat/Svarah) are gated behind sign-in + acceptance, so this uses
`say` (Aman, Rishi, Tara). Audio goes to a scratch dir passed on the command line, never into the repo.
Usage: server/patient-service/.venv/bin/python tools/stt_bench/bench.py <scratch_dir>
"""
import re
import subprocess
import sys
import time
from pathlib import Path

import jiwer
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server/patient-service"))
import stt  # noqa: E402

HERE = Path(__file__).parent
VOICES = ["Aman", "Rishi", "Tara"]
MODELS = ["mlx-community/parakeet-tdt-0.6b-v2", stt.WHISPER]
RISK = ["suicidal thoughts", "suicide", "end your life", "harm yourself", "self harm", "not wake up", "harming someone", "overdose"]
ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def num_words(n: str) -> str:
    if len(n) >= 4:
        return " ".join(ONES[int(d)] for d in n)  # phone numbers: digit by digit
    v = int(n)
    if v < 20:
        return ONES[v]
    if v < 100:
        return TENS[v // 10] + ("" if v % 10 == 0 else " " + ONES[v % 10])
    return ONES[v // 100] + " hundred" + ("" if v % 100 == 0 else " " + num_words(str(v % 100)))


def norm(s: str) -> str:
    s = s.lower().replace("-", " ").replace("dr.", "doctor").replace("’", "'")
    s = re.sub(r"\d+", lambda m: " " + num_words(m.group()) + " ", s)
    s = re.sub(r"[^a-z' ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main(scratch: Path):
    qs = [q.strip() for q in (HERE / "questions.txt").read_text().splitlines() if q.strip()]
    scratch.mkdir(parents=True, exist_ok=True)
    clips = []
    for i, q in enumerate(qs):
        for v in VOICES:
            p = scratch / f"{i:03d}_{v}.wav"
            if not p.exists():
                subprocess.run(["say", "-v", v, "-o", str(p), "--file-format=WAVE", "--data-format=LEI16@16000", q], check=True)
            clips.append((q, v, p))
    print(f"{len(qs)} questions x {len(VOICES)} voices = {len(clips)} clips (synthetic en_IN proxy)")
    rows = []
    for model in MODELS:
        stt.load(model)
        refs, hyps, secs, audio_s, risk_hit, risk_n = [], [], 0.0, 0.0, 0, 0
        per_voice = {v: ([], []) for v in VOICES}
        for q, v, p in clips:
            a, sr = sf.read(p, dtype="float32")
            t = time.perf_counter()
            h = stt.transcribe(a, model)
            secs += time.perf_counter() - t
            audio_s += len(a) / sr
            r, hn = norm(q), norm(h)
            refs.append(r)
            hyps.append(hn)
            per_voice[v][0].append(r)
            per_voice[v][1].append(hn)
            for ph in RISK:
                if ph in r:
                    risk_n += 1
                    risk_hit += ph in hn
                    if ph not in hn:
                        print(f"  RISK MISS [{model.split('/')[-1]} {v}] {q!r} -> {h!r}")
        wer = jiwer.wer(refs, hyps)
        rows.append((model, wer, {v: jiwer.wer(*per_voice[v]) for v in VOICES}, secs / len(clips) * 1000, audio_s / secs, risk_hit, risk_n))
        worst = sorted(zip(refs, hyps), key=lambda x: -jiwer.wer(x[0], x[1]))[:5]
        for r, h in worst:
            print(f"  worst [{model.split('/')[-1]}] {r!r} -> {h!r}")
    print("\n| Model | WER | WER Aman / Rishi / Tara | ms per clip | x real time | Risk phrases recognised |")
    print("|---|---|---|---|---|---|")
    for m, w, pv, ms, rt, rh, rn in rows:
        print(f"| `{m}` | {w:.1%} | {' / '.join(f'{x:.1%}' for x in pv.values())} | {ms:.0f} | {rt:.0f}x | {rh}/{rn} |")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
