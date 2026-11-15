"""Original score for the showcase film: D minor, 64 bpm. Warm detuned pad, felt-piano motif, sub swells, two low impacts
(title and end card), a breath of noise into each scene, convolution reverb, ducked under dialogue. 48 kHz stereo.

  python3 tools/demo/showcase_score.py  ->  demo/showcase/film/score.wav
Timings (film seconds) match the edit in demo/showcase/film/composition (brag-plan.md).
"""
import numpy as np
import soundfile as sf
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SR, TOTAL, BPM = 48000, 91.0, 64.0
TITLE, STACK, END = 11.2, 77.9, 87.0
CUTS = [11.2, 17.2, 28.8, 37.8, 49.1, 67.2, 77.9, 83.4]
DIALOGUE = [(0.0, 11.2), (17.2, 77.9), (83.4, 89.2)]
# Dm  Bb  F  C  | Dm  Bb  Gm  A(sus->maj)
CHORDS = [[50, 53, 57], [46, 50, 53], [41, 45, 48], [48, 52, 55], [50, 53, 57], [46, 50, 53], [43, 46, 50], [45, 49, 52]]
rng = np.random.default_rng(11)
hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)
n = int(TOTAL * SR)
t = np.arange(n) / SR
L, R = np.zeros(n), np.zeros(n)


def add(sig, start, pan=0.0, gain=1.0):
    s = int(start * SR)
    if s >= n:
        return
    sig = sig[: n - s] * gain
    L[s:s + len(sig)] += sig * np.sqrt((1 - pan) / 2)
    R[s:s + len(sig)] += sig * np.sqrt((1 + pan) / 2)


def saw(f, tt, harmonics=10):
    return sum(np.sin(2 * np.pi * f * k * tt) / k for k in range(1, harmonics + 1))


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # one-pole; a few seconds of pad per chord, fast enough
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def intensity(time):
    """0..1: quiet under the cold open, lifts at the title, sits low under dialogue, opens at the stack, resolves."""
    pts = [(0, 0.25), (9, 0.35), (TITLE, 1.0), (16.5, 0.8), (17.2, 0.45), (49, 0.5), (67, 0.6), (STACK, 1.0), (83.4, 0.6), (END, 0.9), (TOTAL, 0.0)]
    xs, ys = zip(*pts)
    return np.interp(time, xs, ys)


bar = 60 / BPM * 4
for b in range(int(TOTAL / bar) + 1):
    start = b * bar
    ch = CHORDS[b % len(CHORDS)]
    dur = bar + 1.5
    tt = np.arange(int(dur * SR)) / SR
    env = np.minimum(tt / 1.2, 1) * np.exp(-np.maximum(tt - bar, 0) / 0.6)
    lift = float(intensity(start + bar / 2))
    for i, m in enumerate(ch):  # pad: two detuned saws per note, filtered, spread
        for det, pan in ((-0.07, -0.6 + i * 0.3), (0.07, 0.6 - i * 0.3)):
            x = saw(hz(m + 12 + det), tt, 8) * env
            add(lowpass(x, 700 + 900 * lift), start, pan, 0.010 * (0.5 + lift))
    sub = np.sin(2 * np.pi * hz(ch[0] - 12) * tt) * env  # sub
    add(sub, start, 0, 0.05 * lift)
    motif = [ch[2] + 24, ch[1] + 24, ch[0] + 24, ch[1] + 24 + (2 if b % 2 else 0)]
    for k, m in enumerate(motif):  # felt piano: soft attack, quick decay, a little inharmonic shimmer
        if lift < 0.3 and k % 2:
            continue
        pt = np.arange(int(3.0 * SR)) / SR
        f = hz(m)
        tone = np.sin(2 * np.pi * f * pt) + 0.35 * np.sin(2 * np.pi * 2.003 * f * pt) * np.exp(-pt / 0.4) + 0.1 * np.sin(2 * np.pi * 3.01 * f * pt) * np.exp(-pt / 0.2)
        piano = tone * np.exp(-pt / 0.9) * np.minimum(pt / 0.012, 1)
        add(lowpass(piano, 2400), start + k * bar / 4 + 0.01 * rng.standard_normal(), (k - 1.5) * 0.25, 0.045 * (0.6 + 0.4 * lift))

for c in CUTS:  # breath of filtered noise into each scene
    d = 0.9
    x = lowpass(rng.standard_normal(int(d * SR)), 1800) * np.linspace(0, 1, int(d * SR)) ** 2.2
    add(x, c - d, rng.uniform(-0.3, 0.3), 0.10)

for at, gain in ((TITLE, 0.10), (END, 0.08)):  # low impact: pitched-down sine thump plus a soft noise tail
    it = np.arange(int(3.5 * SR)) / SR
    thump = np.sin(2 * np.pi * (38 + 40 * np.exp(-it / 0.08)) * it) * np.exp(-it / 0.9)
    tail = lowpass(rng.standard_normal(len(it)), 500) * np.exp(-it / 1.2) * 0.4
    add(thump + tail, at, 0, gain)
for at in (TITLE, STACK):  # rising swell into the big moments
    d = 2.6
    st = np.arange(int(d * SR)) / SR
    sw = sum(np.sin(2 * np.pi * hz(m) * st) for m in (62, 69, 74)) * (st / d) ** 3
    add(sw, at - d, 0, 0.03)

# convolution reverb: decaying stereo noise impulse
ir_len = int(2.8 * SR)
it = np.arange(ir_len) / SR
irL = rng.standard_normal(ir_len) * np.exp(-it / 0.75)
irR = rng.standard_normal(ir_len) * np.exp(-it / 0.75)
irL[0] = irR[0] = 0
wetL = np.fft.irfft(np.fft.rfft(L, 2 * n) * np.fft.rfft(irL, 2 * n))[:n]
wetR = np.fft.irfft(np.fft.rfft(R, 2 * n) * np.fft.rfft(irR, 2 * n))[:n]
mixL, mixR = L + 0.018 * wetL, R + 0.018 * wetR

duck = np.ones(n)
for a, b in DIALOGUE:
    duck[int(a * SR):int(b * SR)] = 0.32
k = int(0.4 * SR)
duck = np.convolve(duck, np.ones(k) / k, "same")
out = np.stack([mixL * duck, mixR * duck], 1)
out[: int(0.5 * SR)] *= np.linspace(0, 1, int(0.5 * SR))[:, None]
out[-int(3 * SR):] *= np.linspace(1, 0, int(3 * SR))[:, None] ** 1.5
out *= 0.5 / np.abs(out).max()  # peak -6 dBFS; the dialogue sits on top
dst = ROOT / "demo/showcase/film/score.wav"
sf.write(dst, out.astype(np.float32), SR, subtype="PCM_24")
print(f"wrote {dst} ({TOTAL} s)")
