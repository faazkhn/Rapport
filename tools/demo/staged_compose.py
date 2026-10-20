"""Compose the staged concept-preview video (demo/Sanvaad_concept_preview.mp4) from the staged Unity takes and the Chitta Twin capture.

Title card -> female take with the Twin over the side panel during the interview -> illustrative learning-curve card -> Arjun cut -> end card.
A "Concept preview · staged" badge stays on screen throughout: replies, voice and brain states are pre-written, not live.

Usage (from Med/): server/patient-service/.venv/bin/python tools/demo/staged_compose.py --twin-in 21.5 --twin-out 160
"""
import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from post import FPS, FONT, H, W, card, probe, run  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "demo" / "raw"
DEVANAGARI = "/System/Library/Fonts/Kohinoor.ttc"
XF = 0.6
BADGE = "Concept preview · staged"


def learning_card(path):
    """Illustrative curves for five brain versions; labelled as targets, not measurements."""
    img = Image.new("RGB", (W, H), (18, 22, 28))
    d = ImageDraw.Draw(img)
    f = lambda s, b=False: ImageFont.truetype(FONT, s, index=1 if b else 0)  # noqa: E731
    d.text((160, 110), "Chitta learns between sessions", font=f(56, True), fill=(240, 240, 240))
    d.text((160, 185), "Experience library + faculty principles + nightly prompt optimisation, gated by safety tests", font=f(30), fill=(170, 178, 190))
    x0, y0, x1, y1 = 220, 340, 1700, 860
    d.line([(x0, y1), (x1, y1)], fill=(90, 98, 110), width=2)
    d.line([(x0, y0), (x0, y1)], fill=(90, 98, 110), width=2)
    vs = ["v0", "v1", "v2", "v3", "v4"]
    xs = [x0 + 60 + i * (x1 - x0 - 120) / 4 for i in range(5)]
    for x, v in zip(xs, vs):
        d.text((x - 16, y1 + 14), v, font=f(28), fill=(170, 178, 190))
    series = [("Realism (faculty blind A/B)", (90, 170, 250), [0.42, 0.55, 0.63, 0.70, 0.74]),
              ("Repetition", (240, 170, 60), [0.38, 0.27, 0.19, 0.14, 0.12]),
              ("Banned-word rate", (200, 120, 220), [0.20, 0.11, 0.06, 0.04, 0.03]),
              ("Invented facts (safety gate)", (110, 200, 140), [0.0, 0.0, 0.0, 0.0, 0.0])]
    for i, (name, col, ys) in enumerate(series):
        pts = [(x, y1 - 8 - v * (y1 - y0 - 20)) for x, v in zip(xs, ys)]
        d.line(pts, fill=col, width=6, joint="curve")
        for p in pts:
            d.ellipse([p[0] - 9, p[1] - 9, p[0] + 9, p[1] + 9], fill=col)
        d.text((160 + i * 420, 262), "●  " + name, font=f(28), fill=col)
    d.text((160, 950), "Illustrative: the planned learning curve, not measured results.", font=f(34, True), fill=(240, 170, 60))
    img.save(path)


def title_card(path):
    img = Image.new("RGB", (W, H), (18, 22, 28))
    d = ImageDraw.Draw(img)
    rows = [("Sanvaad", ImageFont.truetype(FONT, 120, index=1), (240, 240, 240)),
            ("संवाद · dialogue", ImageFont.truetype(DEVANAGARI, 52), (170, 178, 190)),
            ("Embodied psychiatry OSCE simulator with a self-improving patient brain", ImageFont.truetype(FONT, 40), (170, 178, 190)),
            (BADGE + ": planned behaviour, pre-written replies", ImageFont.truetype(FONT, 36), (240, 170, 60))]
    hs = [fo.getbbox("Agय")[3] + 30 for _, fo, _ in rows]
    y = (H - sum(hs)) // 2
    for (t, fo, c), h in zip(rows, hs):
        d.text(((W - d.textlength(t, font=fo)) / 2, y), t, font=fo, fill=c)
        y += h
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--take", default=str(RAW / "Sanvaad_staged.mp4"))
    ap.add_argument("--arjun", default=str(RAW / "Sanvaad_staged_arjun.mp4"))
    ap.add_argument("--twin", default=str(ROOT / "demo" / "staged" / "twin.mp4"), help="600x1080 capture aligned to the take's clock")
    ap.add_argument("--twin-in", type=float, required=True, help="take time (s) the Twin fades in (interview start)")
    ap.add_argument("--twin-out", type=float, required=True, help="take time (s) the Twin fades out (tablet tools start)")
    ap.add_argument("--panel-x", type=int, default=1320, help="left edge of the app's side panel in the 1920 frame")
    ap.add_argument("--arjun-start", type=float, default=14.5, help="Arjun cut: skip his start screen and walk-in")
    ap.add_argument("--trim-end", type=float, default=3.0)
    ap.add_argument("--out", default=str(ROOT / "demo" / "Sanvaad_concept_preview.mp4"))
    a = ap.parse_args()
    title_card(RAW / "staged_title.png")
    learning_card(RAW / "staged_learning.png")
    card(RAW / "staged_arjun.png", [("Same case, male variant", 56, (240, 240, 240), True),
                                    ("Arjun Rao · same clinical facts, different body and voice", 36, (170, 178, 190), False)])
    card(RAW / "staged_end.png", [("Sanvaad (formerly PsychSim)", 64, (240, 240, 240), True),
                                  ("Planned: Chitta brain · Chitta Twin · emotional local voice · turn-taking under 0.7 s · exam close-ups", 30, (170, 178, 190), False),
                                  ("Everything runs on one Mac. No cloud.", 30, (170, 178, 190), False), ("", 20, (0, 0, 0), False),
                                  ("Concept preview: patient replies, voice and brain states in this video are pre-written.", 32, (240, 170, 60), True),
                                  ("Draft clinical content, not yet faculty-validated. For education only.", 30, (240, 170, 60), False)])
    take_s = float(probe(a.take)["format"]["duration"]) - a.trim_end
    segs = [("img", RAW / "staged_title.png", 4.0), ("take", a.take, take_s), ("img", RAW / "staged_learning.png", 6.0)]
    if Path(a.arjun).exists():
        ad = float(probe(a.arjun)["format"]["duration"])
        segs += [("img", RAW / "staged_arjun.png", 2.0), ("vid", a.arjun, ad - a.arjun_start - 0.5, a.arjun_start)]
    segs.append(("img", RAW / "staged_end.png", 6.0))

    inputs, fc = [], []
    for i, (kind, src, dur, *ss) in enumerate(segs):
        if kind == "img":
            inputs += ["-loop", "1", "-t", str(dur), "-i", str(src)]
            fc.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{dur}[a{i}]")
        else:
            inputs += ["-ss", f"{ss[0] if ss else 0:.3f}", "-t", f"{dur:.3f}", "-i", str(src)]
            fc.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS,apad,atrim=0:{dur}[a{i}]")
        fc.append(f"[{i}:v]fps={FPS},scale={W}:{H},format=yuv420p,setsar=1,setpts=PTS-STARTPTS[v{i}]")
    ti = len(segs)
    badge_png = RAW / "staged_badge.png"
    bf = ImageFont.truetype(FONT, 26)
    bw = int(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(BADGE, font=bf)) + 28
    b = Image.new("RGBA", (bw, 46), (18, 22, 28, 204))
    ImageDraw.Draw(b).text((14, 8), BADGE, font=bf, fill=(240, 170, 60))
    b.save(badge_png)
    inputs += ["-i", a.twin, "-loop", "1", "-i", str(badge_png)]
    k = next(i for i, s in enumerate(segs) if s[0] == "take")
    fade = f"fade=t=in:st={a.twin_in}:d=0.6:alpha=1,fade=t=out:st={a.twin_out - 0.6}:d=0.6:alpha=1"
    fc.append(f"[{ti}:v]fps={FPS},scale=600:1080,format=yuva420p,setpts=PTS-STARTPTS+{a.twin_in}/TB,{fade}[tw]")
    fc.append(f"[v{k}][tw]overlay=x={a.panel_x}:y=0:eof_action=pass:enable='between(t,{a.twin_in},{a.twin_out})'[v{k}t]")
    names = [f"v{i}t" if i == k else f"v{i}" for i in range(len(segs))]
    cv, ca, off = names[0], "a0", 0.0
    for i in range(1, len(segs)):
        off += segs[i - 1][2] - XF
        fc.append(f"[{cv}][{names[i]}]xfade=transition=fade:duration={XF}:offset={off:.3f}[xv{i}]")
        fc.append(f"[{ca}][a{i}]acrossfade=d={XF}[xa{i}]")
        cv, ca = f"xv{i}", f"xa{i}"
    fc.append(f"[{cv}][{ti + 1}:v]overlay=x=28:y=28:shortest=1[vout]")
    fc.append(f"[{ca}]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]")
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "18", "-r", str(FPS), "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out])
    info = probe(a.out)
    print("OUT", a.out, info["format"]["duration"])


if __name__ == "__main__":
    main()
