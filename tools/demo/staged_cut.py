"""Tighten a staged take: shrink each dead silence in the interview to the planned turn gap, and write the turn times on the cut clock.

When the editor is not frontmost the Recorder's game clock runs slow, the doctor's mic injection lags behind the audible line, and the
take gets long silences between the doctor and the patient. The video itself is smooth (constant-rate capture), so the silences are
cut (with a short dissolve) down to GAP_DP (doctor -> patient, the planned 0.6 s latency) and GAP_PD (patient -> next doctor line).

Usage (from Med/): server/patient-service/.venv/bin/python tools/demo/staged_cut.py demo/raw/Sanvaad_staged.mp4 female
Writes <take>_cut.mp4 and demo/staged/turn_times_<variant>.json.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve, resample_poly

ROOT = Path(__file__).resolve().parents[2]
GAP_DP, GAP_PD, XF, MIN_SIL = 0.6, 0.8, 0.2, 1.2
SR = 16000


def audio(path):
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), f.name], check=True)
        return sf.read(f.name)[0]


def align(v, wavs):
    """Start time of each patient WAV in the take, searched in order after the previous match."""
    starts, cur = [], 0
    for w in wavs:
        probe = w[:SR * 2]
        x = fftconvolve(v[cur:], probe[::-1], "valid")
        s = cur + int(np.argmax(np.abs(x)))
        starts.append(s / SR)
        cur = s + len(w)
    return starts


def silences(loud, lo, hi):
    """(start, end) of quiet runs >= MIN_SIL between lo and hi seconds."""
    out, i, n = [], int(lo * SR), int(hi * SR)
    while i < n:
        if loud[i]:
            i += 1
            continue
        j = i
        while j < n and not loud[j]:
            j += 1
        if (j - i) / SR >= MIN_SIL:
            out.append((i / SR, j / SR))
        i = j
    return out


def main():
    take, variant = Path(sys.argv[1]), sys.argv[2]
    script = json.loads((ROOT / "demo/staged/script.json").read_text())
    turns = script["arjun_turns" if variant == "male" else "turns"]
    wavs = []
    for i in range(len(turns)):
        w, wsr = sf.read(ROOT / f"demo/staged/audio/{variant}_{i}.wav")
        wavs.append(resample_poly(w, SR, wsr) if wsr != SR else w)
    v = audio(take)
    dur = len(v) / SR
    loud = np.convolve(np.abs(v), np.ones(160) / 160, "same") > 0.01
    ps = align(v, wavs)
    pe = [s + len(w) / SR for s, w in zip(ps, wavs)]
    # cuts: dead air between the first doctor line and the last reply, never inside a patient line
    j = int((ps[0] - 0.05) * SR)
    while j > 0 and not loud[j]:
        j -= 1
    while j > 0 and not (np.all(~loud[max(0, j - int(0.6 * SR)):j])):
        j -= 1
    lo, hi = j / SR, pe[-1]  # from the first doctor line (the walk-in stays whole) to the last reply
    cuts = []
    for a, b in silences(loud, lo, hi):
        if any(s < b and a < e for s, e in zip(ps, pe)) and not any(abs(b - s) < 0.15 for s in ps):
            continue
        gap = GAP_DP if any(abs(b - s) < 0.15 for s in ps) else GAP_PD
        if b - a > gap + XF:
            cuts.append((a + gap / 2, b - gap / 2))
    for a, b in cuts:
        print(f"cut {a:7.2f}-{b:7.2f} ({b - a:5.2f}s)")
    # the patient's own audio begins exactly at ps; a silence ending at ps is the doctor->patient gap
    keep, t = [], 0.0
    for a, b in cuts:
        keep.append((t, a + XF / 2))
        t = b - XF / 2
    keep.append((t, dur))

    def to_cut(x):
        out = 0.0
        for k, (a, b) in enumerate(keep):
            if x <= b:
                return out + max(0.0, x - a) - k * XF
            out += b - a
        return out - (len(keep) - 1) * XF

    times = []
    for i in range(len(turns)):
        j = int(ps[i] * SR) - int(0.05 * SR)
        while j > 0 and not loud[j]:
            j -= 1
        de = j / SR
        q = 0
        while j > 0:
            q = q + 1 if not loud[j] else 0
            if q >= 0.6 * SR:
                break
            j -= 1
        times.append({"turn": i + 1, "doctor_start": round(to_cut((j + q) / SR), 2), "doctor_end": round(to_cut(de), 2),
                      "patient_start": round(to_cut(ps[i]), 2), "patient_end": round(to_cut(pe[i]), 2)})
    for a_, b_ in zip(times, times[1:]):  # the patient's own pauses can fool the doctor-start search
        b_["doctor_start"] = max(b_["doctor_start"], round(a_["patient_end"] + 0.05, 2))
    for t_ in times:
        assert t_["doctor_start"] <= t_["doctor_end"] < t_["patient_start"] < t_["patient_end"], t_
    out_times = ROOT / f"demo/staged/turn_times_{variant}.json"
    out_times.write_text(json.dumps(times, indent=1))

    fc, n = [], len(keep)
    for k, (a, b) in enumerate(keep):
        fc.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{k}]")
        fc.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[a{k}]")
    cv, ca, off = "v0", "a0", 0.0
    for k in range(1, n):
        off += keep[k - 1][1] - keep[k - 1][0] - XF
        fc.append(f"[{cv}][v{k}]xfade=transition=fade:duration={XF}:offset={off:.3f}[xv{k}]")
        fc.append(f"[{ca}][a{k}]acrossfade=d={XF}[xa{k}]")
        cv, ca = f"xv{k}", f"xa{k}"
    out = take.with_name(take.stem + "_cut.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(take), "-filter_complex", ";".join(fc), "-map", f"[{cv}]", "-map", f"[{ca}]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-r", "60", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    str(out)], check=True)
    print(f"{len(cuts)} cuts, {dur:.1f}s -> {to_cut(dur):.1f}s; {out}; {out_times}")
    for t_ in times:
        print(t_, "latency", round(t_["patient_start"] - t_["doctor_end"], 2))


if __name__ == "__main__":
    main()
