#!/usr/bin/env python3
"""Beat-segmented narrated video, narrated with Google Cloud TTS (Chirp3-HD British).

Usage: build_video.py <frames_dir> <beats_json> <out_mp4>
  frames_dir: a CDP screencast dir (NNNNN.jpg + frames.jsonl + timeline.json)
  beats_json: [{"label", "next"|null, "text", ...opts}, ...] where the window is
              [t(label), t(next or END)) against timeline.json labels.

Per-beat options:
  "mode": "tail" (default) — keep only the last `tail` seconds of the window: the
          rendered-result hold. Right for beats that span a long LLM wait.
  "mode": "full" — keep the WHOLE window, playing dense-frame stretches (typing,
          cursor motion) in near real time and compressing static gaps to `clamp`
          seconds. Right for human-interaction beats.
  "tail": seconds (default 7.0)   "clamp": max still-gap seconds (default 1.2;
          use ~0.8 for full-mode beats so waits inside them stay tight).

Frames only arrive when pixels change, so typing yields dense frames (plays real
time) while a "Thinking…" wait yields sparse ones (auto-compressed by clamp).
"""
import json, os, subprocess, base64, urllib.request, sys

REC = sys.argv[1]
BEATS = json.load(open(sys.argv[2]))
OUT = sys.argv[3]
WORK = os.path.join(REC, "build"); os.makedirs(WORK, exist_ok=True)
VOICE = "en-GB-Chirp3-HD-Achernar"   # British, natural/generative
TAIL = 7.0
CLAMP = 1.2
PAD_AFTER = 1.0

PROJ = subprocess.run(["gcloud", "config", "get-value", "project"], capture_output=True, text=True).stdout.strip()
TOKEN = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True).stdout.strip()

# No `gcloud auth`? Swap this for the edge-tts fallback (free, no auth) — see
# SKILL.md "TTS without gcloud" for the drop-in subprocess-based replacement.
def tts(text, path):
    body = json.dumps({"input": {"text": text}, "voice": {"languageCode": "en-GB", "name": VOICE},
                       "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.0}}).encode()
    req = urllib.request.Request("https://texttospeech.googleapis.com/v1/text:synthesize", data=body,
        headers={"Authorization": "Bearer " + TOKEN, "X-Goog-User-Project": PROJ, "Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req))
    open(path, "wb").write(base64.b64decode(d["audioContent"]))

frames = [json.loads(l) for l in open(os.path.join(REC, "frames.jsonl"))]
timeline = json.load(open(os.path.join(REC, "timeline.json")))
END = frames[-1]["t"] + 0.5

def label_t(lbl):
    for x in timeline:
        if x.get("label") == lbl:
            return x["t"]
    return None

def frames_in(a, b):
    return [f for f in frames if a <= f["t"] < b]

concat = []
for beat in BEATS:
    label, nxt, narr = beat["label"], beat.get("next"), beat["text"]
    mode = beat.get("mode", "tail")
    tail = float(beat.get("tail", TAIL))
    clamp = float(beat.get("clamp", 0.8 if mode == "full" else CLAMP))
    t0 = label_t(label)
    if t0 is None:
        print("WARN no label", label); continue
    t1 = label_t(nxt) if nxt else END
    if t1 is None:
        t1 = END
    win_start = t0 if mode == "full" else max(t0, t1 - tail)
    fr = frames_in(win_start, t1)
    if not fr:
        fr = frames_in(t0, t1)
    if not fr:
        print("WARN no frames", label); continue
    aud = os.path.join(WORK, label + ".mp3"); tts(narr, aud)
    adur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", aud], capture_output=True, text=True).stdout.strip())
    durs = []
    for i, f in enumerate(fr):
        nt = fr[i + 1]["t"] if i + 1 < len(fr) else t1
        durs.append(max(0.04, min(clamp, nt - f["t"])))
    vis = sum(durs); target = adur + PAD_AFTER
    if target > vis:
        durs[-1] += (target - vis)
    bl = os.path.join(WORK, label + ".txt")
    with open(bl, "w") as g:
        for f, d in zip(fr, durs):
            g.write("file '%s'\n" % os.path.join(REC, '%05d.jpg' % f['i'])); g.write("duration %.3f\n" % d)
        g.write("file '%s'\n" % os.path.join(REC, '%05d.jpg' % fr[-1]['i']))
    segv = os.path.join(WORK, label + "_v.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", bl,
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-pix_fmt", "yuv420p", "-r", "30", "-c:v", "libx264", "-crf", "23", segv], check=True)
    # Sync note: `durs[-1] += (target - vis)` above already stretched the video's
    # frame-hold list so its duration is >= adur + PAD_AFTER, i.e. the video is
    # never shorter than the narration. That's what makes `-shortest` safe here —
    # it's a belt-and-braces trim on an already-reconciled pair, not the sync
    # mechanism itself. `apad` here is a bare/unbounded pad (no `whole_dur`); it
    # only "works" because the following `-shortest` cuts it back to match video.
    # Don't copy this `apad` + `-shortest` combo into a fresh merge step where
    # durations haven't already been reconciled — there, use the explicit
    # `adelay=<ms>|<ms>,apad=whole_dur=<video_seconds>` pattern (delay the voice
    # in, pad silence out to the exact video length) and `tpad=stop_mode=clone`
    # to extend the video if narration would run long. See SKILL.md "FFmpeg sync
    # rules" for the full explanation.
    seg = os.path.join(WORK, label + ".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", segv, "-i", aud,
        "-filter_complex", "[1:a]apad[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", seg], check=True)
    concat.append("file '%s'" % seg)
    print("%s[%s]: frames=%d vis=%.1f narr=%.1f -> %.1fs" % (label, mode, len(fr), vis, adur, max(vis, target)))

cl = os.path.join(WORK, "all.txt"); open(cl, "w").write("\n".join(concat) + "\n")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", cl, "-c", "copy", OUT], check=True)
print("OUTPUT", OUT, subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", OUT], capture_output=True, text=True).stdout.strip() + "s")
