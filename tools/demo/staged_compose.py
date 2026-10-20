"""Compose the staged demo video (demo/Rapport_demo_staged.mp4): the female take with the Digital Twin over the side panel during
the interview, then the Arjun take. No title, end or badge cards.

Usage (from Med/): server/patient-service/.venv/bin/python tools/demo/staged_compose.py --twin-in 20.3 --twin-out 188.5
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from post import FPS, H, W, probe, run  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "demo" / "raw"
XF = 0.6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--take", default=str(RAW / "Rapport_staged_cut.mp4"))
    ap.add_argument("--arjun", default=str(RAW / "Rapport_staged_arjun_cut.mp4"))
    ap.add_argument("--twin", default=str(ROOT / "demo" / "staged" / "twin.mp4"), help="600x1080 capture aligned to the take's clock")
    ap.add_argument("--twin-in", type=float, required=True, help="take time (s) the Twin fades in (interview start)")
    ap.add_argument("--twin-out", type=float, required=True, help="take time (s) the Twin fades out (tablet tools start)")
    ap.add_argument("--panel-x", type=int, default=1320, help="left edge of the app's side panel in the 1920 frame")
    ap.add_argument("--arjun-start", type=float, default=14.5, help="Arjun cut: skip his start screen and walk-in")
    ap.add_argument("--trim-end", type=float, default=3.0)
    ap.add_argument("--out", default=str(ROOT / "demo" / "Rapport_demo_staged.mp4"))
    a = ap.parse_args()
    segs = [(a.take, float(probe(a.take)["format"]["duration"]) - a.trim_end, 0.0)]
    if Path(a.arjun).exists():
        segs.append((a.arjun, float(probe(a.arjun)["format"]["duration"]) - a.arjun_start - 0.5, a.arjun_start))

    inputs, fc = [], []
    for i, (src, dur, ss) in enumerate(segs):
        inputs += ["-ss", f"{ss:.3f}", "-t", f"{dur:.3f}", "-i", str(src)]
        fc.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS,apad,atrim=0:{dur}[a{i}]")
        fc.append(f"[{i}:v]fps={FPS},scale={W}:{H},format=yuv420p,setsar=1,setpts=PTS-STARTPTS[v{i}]")
    ti = len(segs)
    inputs += ["-i", a.twin]
    fade = f"fade=t=in:st={a.twin_in}:d=0.6:alpha=1,fade=t=out:st={a.twin_out - 0.6}:d=0.6:alpha=1"
    fc.append(f"[{ti}:v]fps={FPS},scale=600:1080,format=yuva420p,setpts=PTS-STARTPTS+{a.twin_in}/TB,{fade}[tw]")
    fc.append(f"[v0][tw]overlay=x={a.panel_x}:y=0:eof_action=pass:enable='between(t,{a.twin_in},{a.twin_out})'[x0]")
    cv, ca = "x0", "a0"
    if len(segs) > 1:
        fc.append(f"[x0][v1]xfade=transition=fade:duration={XF}:offset={segs[0][1] - XF:.3f}[x1]")
        fc.append(f"[a0][a1]acrossfade=d={XF}[xa1]")
        cv, ca = "x1", "xa1"
    fc.append(f"[{ca}]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]")
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", f"[{cv}]", "-map", "[aout]",
         "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "18", "-r", str(FPS), "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out])
    print("OUT", a.out, probe(a.out)["format"]["duration"])


if __name__ == "__main__":
    main()
