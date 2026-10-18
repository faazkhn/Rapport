"""Post-process the recorded demo take into demo/PsychSim_demo_v1.mp4.

Adds a title card and an end card (crossfaded), soft room tone under the dialogue, loudness normalised to -16 LUFS,
H.264 high profile 1920x1080 60 fps with AAC 192k. Also writes check frames (one every 10 s) and 6 stills.

Usage (from Med/): server/patient-service/.venv/bin/python tools/demo/post.py [demo/raw/PsychSim_take.mp4]
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
    take = Path(sys.argv[1]) if len(sys.argv) > 1 else DEMO / "raw" / "PsychSim_take.mp4"
    work = DEMO / "raw"
    white, grey, amber = (240, 240, 240), (170, 178, 190), (240, 170, 60)
    card(work / "title.png", [("PsychSim", 110, white, True), ("Clinical encounter simulator", 48, grey, False),
                              ("For education only", 40, amber, False)])
    card(work / "end.png", [("Coming next", 56, white, True), ("Voice input  ·  10 cases  ·  VR on Quest 3S", 44, grey, False),
                            ("", 20, grey, False), ("Draft content, not yet faculty-validated", 40, amber, False),
                            ("Patient replies in this take were scripted. The live build generates them with Grok (xAI).", 30, grey, False)])
    take_s = float(probe(take)["format"]["duration"]) - TRIM_END
    out = DEMO / "PsychSim_demo_v1.mp4"
    total = TITLE_S + take_s + END_S - 2 * XF
    fc = (
        f"[0:v]fps={FPS},format=yuv420p,setsar=1[t];"
        f"[1:v]fps={FPS},scale={W}:{H},format=yuv420p,setsar=1[m];"
        f"[2:v]fps={FPS},format=yuv420p,setsar=1[e];"
        f"[t][m]xfade=transition=fade:duration={XF}:offset={TITLE_S - XF}[tm];"
        f"[tm][e]xfade=transition=fade:duration={XF}:offset={TITLE_S + take_s - 2 * XF}[v];"
        f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay={int((TITLE_S - XF) * 1000)}|{int((TITLE_S - XF) * 1000)}[dlg];"
        f"anoisesrc=color=brown:amplitude=0.012:sample_rate=48000:duration={total},lowpass=f=400,"
        f"afade=t=in:d=1.5,afade=t=out:st={total - 2}:d=2,aformat=channel_layouts=stereo[tone];"
        f"[dlg][tone]amix=inputs=2:duration=longest:normalize=0,atrim=0:{total},loudnorm=I=-16:TP=-1.5:LRA=11,"
        f"aresample=48000[a]"
    )
    run(["ffmpeg", "-y", "-loop", "1", "-t", str(TITLE_S), "-i", work / "title.png", "-t", f"{take_s:.3f}", "-i", take,
         "-loop", "1", "-t", str(END_S), "-i", work / "end.png", "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "18", "-r", str(FPS), "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])

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
