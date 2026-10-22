"""Post-process the recorded demo take into demo/Rapport_demo_v3.mp4 (or --out).

Adds a title card and an end card (crossfaded), soft room tone under the dialogue, loudness normalised to -16 LUFS,
H.264 high profile 1920x1080 60 fps with AAC 192k. Also writes check frames (one every 10 s) and 6 stills.

Usage (from Med/): server/patient-service/.venv/bin/python tools/demo/post.py [demo/raw/Rapport_take.mp4] [--out demo/Rapport_demo_v3.mp4]
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo"
W, H, FPS = 1920, 1080, 60
TITLE_S, END_S, XF = 3.5, 5.5, 0.6
TRIM_END = 3.0   # the take ends on a long score-screen hold; keeps the cut under 3 minutes
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"


def card(path, lines):
    """lines: (text, size, rgb, bold) centred vertically as a block."""
    img = Image.new("RGB", (W, H), (18, 22, 28))
    d = ImageDraw.Draw(img)
    fonts = [ImageFont.truetype(FONT, size, index=1 if bold else 0) for _, size, _, bold in lines]
    heights = [f.getbbox("Ag")[3] + 24 for f in fonts]
    y = (H - sum(heights)) // 2
    for (text, _, rgb, _), f, h in zip(lines, fonts, heights):
        d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=rgb)
        y += h
    img.save(path)


def run(cmd):
    print(" ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
                          "-of", "json", str(path)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("take", nargs="?", default=str(DEMO / "raw" / "Rapport_take.mp4"))
    ap.add_argument("--arjun", default=str(DEMO / "raw" / "Rapport_take_arjun.mp4"), help="male-variant take; a 10 s cut is inserted ('' for none)")
    ap.add_argument("--arjun-start", type=float, default=None, help="start of the Arjun cut in its take (default: 10 s before its end)")
    ap.add_argument("--trim-start", type=float, default=0.0)
    ap.add_argument("--trim-end", type=float, default=TRIM_END)
    ap.add_argument("--out", default=str(DEMO / "Rapport_demo_v3.mp4"))
    ap.add_argument("--latency", default="", help="measured median, e.g. '1.4 s'")
    a = ap.parse_args()
    take, work = Path(a.take), DEMO / "raw"
    white, grey, amber = (240, 240, 240), (170, 178, 190), (240, 170, 60)
    card(work / "title.png", [("Rapport", 110, white, True), ("Psychiatry OSCE simulator with a Digital Twin patient", 48, grey, False),
                              ("For education only", 40, amber, False)])
    card(work / "end.png", [("Measured voice latency (doctor stops to patient speaks): " + (a.latency or "see docs/latency.md"), 36, white, True),
                            ("Everything runs on one Mac: Parakeet STT · local Gemma 4 E4B · Qwen3-TTS", 32, grey, False),
                            ("Next: faculty review · blind A/B of the learning loop · more cases · VR on Quest 3S", 32, grey, False),
                            ("", 20, grey, False), ("Draft clinical content, not yet faculty-validated", 40, amber, False),
                            ("Dr. Faaz's lines are synthesised (KittenTTS Hugo) and fed through the live microphone path.", 26, grey, False),
                            ("Patient replies are generated live by the local model. One continuous take, no cuts.", 26, grey, False)])
    take_s = float(probe(take)["format"]["duration"]) - a.trim_end - a.trim_start
    segs = [("img", work / "title.png", TITLE_S), ("vid", take, take_s, a.trim_start)]
    arjun = Path(a.arjun)
    if a.arjun and arjun.exists():
        ad = float(probe(arjun)["format"]["duration"])
        card(work / "arjun.png", [("Same case, male variant", 56, white, True), ("Arjun Rao · same clinical facts, different body and voice", 36, grey, False)])
        segs += [("img", work / "arjun.png", 2.0), ("vid", arjun, 10.0, a.arjun_start if a.arjun_start is not None else max(0.0, ad - 10.5))]
    segs.append(("img", work / "end.png", END_S))
    out = Path(a.out)
    inputs, vf, af = [], [], []
    for i, sg in enumerate(segs):
        if sg[0] == "img":
            inputs += ["-loop", "1", "-t", str(sg[2]), "-i", sg[1]]
            vf.append(f"[{i}:v]fps={FPS},scale={W}:{H},format=yuv420p,setsar=1[v{i}]")
            af.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{sg[2]}[a{i}]")
        else:
            inputs += ["-ss", f"{sg[3]:.3f}", "-t", f"{sg[2]:.3f}", "-i", sg[1]]
            vf.append(f"[{i}:v]fps={FPS},scale={W}:{H},format=yuv420p,setsar=1,setpts=PTS-STARTPTS[v{i}]")
            af.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS,apad,atrim=0:{sg[2]}[a{i}]")
    # chain crossfades
    durs = [sg[2] for sg in segs]
    chain_v, chain_a, off = "v0", "a0", 0.0
    xf = []
    for i in range(1, len(segs)):
        off += durs[i - 1] - XF
        xf.append(f"[{chain_v}][v{i}]xfade=transition=fade:duration={XF}:offset={off:.3f}[xv{i}]")
        xf.append(f"[{chain_a}][a{i}]acrossfade=d={XF}[xa{i}]")
        chain_v, chain_a = f"xv{i}", f"xa{i}"
        off -= 0  # offsets accumulate on the shortened chain
    total = sum(durs) - XF * (len(segs) - 1)
    fc = ";".join(vf + af + xf) + (f";anoisesrc=color=brown:amplitude=0.012:sample_rate=48000:duration={total},lowpass=f=400,"
                                   f"afade=t=in:d=1.5,afade=t=out:st={total - 2}:d=2,aformat=channel_layouts=stereo[tone];"
                                   f"[{chain_a}][tone]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]")
    run(["ffmpeg", "-y", *inputs, "-filter_complex", fc, "-map", f"[{chain_v}]", "-map", "[a]",
         "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "18", "-r", str(FPS), "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])

    # teaser: <= 20 s, <= 10 MB, from the interview
    teaser = ROOT / "docs" / "media" / "teaser.mp4"
    teaser.parent.mkdir(parents=True, exist_ok=True)
    tstart = TITLE_S + min(60.0, take_s * 0.35)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{tstart:.2f}", "-t", "18", "-i", out, "-vf", "scale=1280:-2", "-c:v", "libx264", "-crf", "28",
         "-preset", "slow", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", teaser])
    print("teaser", teaser, round(teaser.stat().st_size / 1e6, 1), "MB")

    info = probe(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    dur = float(info["format"]["duration"])
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    print(f"OUT {out} {v['width']}x{v['height']} {v['r_frame_rate']} fps audio={has_audio} {dur:.1f} s")
    assert (v["width"], v["height"]) == (W, H) and has_audio and v["r_frame_rate"] == f"{FPS}/1"

    checks = work / "check"
    checks.mkdir(exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-i", out, "-vf", "fps=1/10,scale=960:-1", checks / "f%03d.png"])
    stills = DEMO / "stills"
    stills.mkdir(exist_ok=True)
    for i, frac in enumerate((0.08, 0.2, 0.42, 0.6, 0.85, 0.95), 1):
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{dur * frac:.2f}", "-i", out, "-frames:v", "1", stills / f"still_{i}.png"])


if __name__ == "__main__":
    main()
