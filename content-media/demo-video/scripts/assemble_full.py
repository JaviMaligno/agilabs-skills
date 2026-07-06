#!/usr/bin/env python3
"""Concatenate the per-journey clips into the full demo video.
Usage: assemble_full.py <out.mp4> <clip1.mp4> <clip2.mp4> ...
All clips come from build_video.py (same 1600x1000 / h264 yuv420p / 30fps / aac),
so we re-encode through a uniform filter to guarantee a clean concat with audio.
"""
import sys, subprocess, os, tempfile

OUT = sys.argv[1]
CLIPS = sys.argv[2:]
if not CLIPS:
    print("no clips"); sys.exit(1)

# Normalise each clip (same SAR/fps/audio) then concat via the demuxer.
work = tempfile.mkdtemp(prefix="assemble_")
norm = []
for i, c in enumerate(CLIPS):
    if not os.path.exists(c):
        print(f"SKIP missing {c}"); continue
    o = os.path.join(work, f"n{i}.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", c,
        "-vf", "scale=1600:1000:force_original_aspect_ratio=decrease,pad=1600:1000:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
        "-c:v", "libx264", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", o], check=True)
    norm.append(o)

lst = os.path.join(work, "list.txt")
open(lst, "w").write("\n".join(f"file '{n}'" for n in norm) + "\n")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
    "-i", lst, "-c", "copy", OUT], check=True)
dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
    "-of", "csv=p=0", OUT], capture_output=True, text=True).stdout.strip()
print(f"OUTPUT {OUT}  ({len(norm)} clips, {dur}s)")
