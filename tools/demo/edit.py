"""Cut the raw take down to the kept exchanges (demo/edit.json: [[start, end], ...] in seconds) with short crossfades.
The cuts only remove waiting time between a doctor line and the reply, and whole exchanges; nothing inside a line is changed.
Usage: .venv/bin/python tools/demo/edit.py demo/raw/Rapport_take.mp4 demo/edit.json demo/raw/Rapport_take_edit.mp4
"""
import json
import subprocess
import sys

XF = 0.25
src, spec, out = sys.argv[1:4]
keep = json.load(open(spec))["keep"]
inputs, parts = [], []
for i, (a, b) in enumerate(keep):
    inputs += ["-ss", f"{a:.2f}", "-t", f"{b - a:.2f}", "-i", src]
    parts.append(f"[{i}:v]fps=60,setpts=PTS-STARTPTS,format=yuv420p[v{i}];[{i}:a]aresample=48000,asetpts=PTS-STARTPTS[a{i}]")
v, a, off, fc = "v0", "a0", 0.0, parts
for i in range(1, len(keep)):
    off += keep[i - 1][1] - keep[i - 1][0] - XF
    fc.append(f"[{v}][v{i}]xfade=transition=fade:duration={XF}:offset={off:.3f}[xv{i}];[{a}][a{i}]acrossfade=d={XF}[xa{i}]")
    v, a = f"xv{i}", f"xa{i}"
subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc), "-map", f"[{v}]", "-map", f"[{a}]",
                "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-c:a", "aac", "-b:a", "256k", out], check=True)
print("edited", out, round(sum(b - a for a, b in keep) - XF * (len(keep) - 1), 1), "s")
