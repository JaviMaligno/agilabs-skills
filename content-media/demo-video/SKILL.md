---
name: demo-video
description: Produce narrated product demo/verification videos of any web app by driving a real Chrome over CDP (natural cursor, human typing), recording a screencast, and assembling beat-narrated MP4s with Google Cloud TTS. Use when asked to record a demo video, product walkthrough, or verification evidence video.
---

# Demo Video — CDP screencast + Google TTS

Drive a real, SSO'd Chrome via the DevTools protocol, record frames while a declarative
step script interacts with the app (visible cursor, human typing), then narrate and
assemble per-beat with Google Cloud TTS (British Chirp3-HD) and ffmpeg.

**Scripts live in `scripts/` next to this file** — copy them into the target repo
(e.g. `<repo>/scripts/demo-video/`) or run them from here. They are app-agnostic;
only the per-video `steps_*.json` + `beats_*.json` are app-specific.

## Prerequisites

```bash
which ffmpeg || brew install ffmpeg
gcloud auth print-access-token >/dev/null && echo TTS-auth OK   # Google Cloud TTS (REST)
python3 -c "import websockets" || pip install websockets
```

No `gcloud auth` on this machine/account? Skip straight to
[TTS without gcloud](#tts-without-gcloud-edge-tts-fallback) below — `edge-tts` needs
no credentials at all.

## 1. Launch Chrome with CDP (SSO once, profile persists)

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 --user-data-dir=/tmp/cdp-demo \
  --no-first-run --force-device-scale-factor=2 --window-size=1600,1000 "<APP_URL>" &
```

The user logs in once (SSO persists in the profile across relaunches). Get the page ws:

```bash
WS=$(curl -s localhost:9222/json | python3 -c "import sys,json; ps=[p for p in json.load(sys.stdin) if p.get('type')=='page']; ps.sort(key=lambda p:'<APP_HOST_FRAGMENT>' in p.get('url',''),reverse=True); print(ps[0]['webSocketDebuggerUrl'])")
```

## 2. Explore & dry-run (no recording)

- `python3 scripts/cdpeval.py "$WS" "<js>"` — one-shot eval (inspect DOM, find buttons/inputs).
- `python3 scripts/drive.py "$WS" steps.json` — run a step script without recording;
  prints final page text. Use to map the app's flow and validate markers BEFORE recording.
  (drive.py disables the HTTP cache, so it also picks up a freshly deployed frontend.)

## 3. Write the step script (steps_*.json)

A JSON array; each step is one of:

```jsonc
{"eval": "<js, awaitPromise>", "label": "beat_name"}   // label marks a beat boundary
{"sleep": 2.0}
{"waitjs": "<js boolean>", "timeout": 130, "poll": 2.0}
{"setfiles": "/abs/file.png", "selector": "input[type=file]"}  // CDP upload (JS can't)
{"navigate": "https://..."}
```

**Naturalness helpers** are auto-injected (see `scripts/helpers.js`) — use them so the
video shows a human-looking cursor and typing:

- `window.__click('Button text' | 'css:selector')` — fake cursor glides (eased), click
  ripple, then clicks. Matches buttons/links by contained text, or `css:` for a selector.
- `window.__typeChat('text', cps)` — types char-by-char into the app's `<textarea>`.
- `window.__typeIn(elOrQuery, 'text', cps)` — same for any input (React-safe: native
  value setter + input events). E.g. fill a form's inputs one by one so it's VISIBLE.
- `window.__moveTo(q)` / `window.__findEl(q)` — cursor motion / lookup.

Define app-specific test helpers in the first `eval` (e.g. `window.__has(re)`,
`window.__done(m)` = marker present AND no "Thinking…" spinner).

**Step-writing rules (hard-won):**
- End-of-turn detection: wait for a stable marker **AND** the absence of the app's
  busy indicator — a card can render while the agent/backend is still finishing.
- If a confirmation widget appears mid-turn, confirm it ONLY after the turn ends,
  or the turn's final state snapshot can overwrite the deterministic change.
- Label the step that STARTS each visual phase; the beat window runs to the next label.
- Interactions the viewer must see (typing a reply, filling a form) get their own label.

## 4. Record

```bash
python3 scripts/screencast.py "$WS" /tmp/rec/<video> steps.json
# -> NNNNN.jpg frames + frames.jsonl (timestamps) + timeline.json (label marks)
```

Gotchas: do **NOT** add `Network.setCacheDisabled` to screencast.py (it starves the ws
and CDP calls time out — record over an already-loaded page; relaunch Chrome after a
frontend deploy). Keep `waitjs` polls ≥ 2s on long backend turns. Frames only arrive
when pixels change, so cost scales with motion, not duration.

## 5. Narrate & build (beats_*.json)

```jsonc
[
  {"label": "intro", "next": "act", "tail": 8, "text": "Narration for this beat…"},
  {"label": "act", "next": null, "mode": "full", "clamp": 0.7, "text": "…"}
]
```

- Window = `[t(label), t(next|END))` against timeline.json.
- `mode: "tail"` (default): keep only the last `tail` seconds — the rendered-result
  hold. Right for beats spanning a long backend/LLM wait.
- `mode: "full"`: whole window; dense-frame stretches (typing, cursor) play near real
  time, static gaps compress to `clamp` seconds. Right for human-interaction beats.
- Narration is Google Cloud TTS `en-GB-Chirp3-HD-Achernar` (change VOICE in
  build_video.py); auth = `gcloud auth print-access-token` + project header.

```bash
python3 scripts/build_video.py /tmp/rec/<video> beats.json out.mp4      # per-beat TTS + ffmpeg
python3 scripts/assemble_full.py final.mp4 clip1.mp4 clip2.mp4 ...      # concat (re-encodes uniformly)
```

### TTS without gcloud (edge-tts fallback)

Google Cloud TTS (Chirp3-HD) is the recommended default — most natural voice, and
`build_video.py` is wired for it. If `gcloud auth` isn't available (no GCP project,
no billing, working from an account without access), use **`edge-tts`** instead: a
free, no-auth CLI that calls Microsoft Edge's neural voices.

```bash
uv tool install edge-tts   # or: pip install edge-tts
edge-tts --list-voices | grep en-GB          # pick a voice, e.g. en-GB-SoniaNeural
edge-tts --voice en-GB-SoniaNeural --text "Narration text" --write-media out.mp3
```

To use it in `build_video.py`, swap the `tts()` function's body for a subprocess
call instead of the Google REST request:

```python
def tts(text, path):
    subprocess.run(["edge-tts", "--voice", "en-GB-SoniaNeural", "--text", text,
                     "--write-media", path], check=True)
```

Notes: `edge-tts` needs internet access (it's calling Microsoft's service, just
without an API key/auth flow) and use `--write-media` for the output flag (not
`-f`). Voice durations vary slightly run-to-run even for identical text — harmless
for a one-off build, but if you regenerate narration for a beat you've already
timed against, expect the sync math in `build_video.py` to re-derive slightly
different padding.

## FFmpeg sync rules (audio vs video length)

These hold regardless of which script is doing the muxing:

- **Never use `-shortest`** when merging a narration track onto a video clip as
  your *primary* sync mechanism — it silently truncates whichever stream is
  longer, cutting narration mid-sentence or dropping trailing video.
- **Pad audio to the exact video length** with `adelay` (silence before narration
  starts) + `apad=whole_dur=<video_seconds>` (silence out to the exact video
  duration) — not a bare `apad`, which pads by an unbounded amount and only
  "works" if you then rely on `-shortest` to cut it back down:
  ```bash
  ffmpeg -y -i video.mp4 -i narration.mp3 \
    -filter_complex "[1:a]adelay=DELAY_MS|DELAY_MS,apad=whole_dur=VIDEO_DURATION[a]" \
    -map 0:v -map "[a]" -c:v copy -c:a aac out.mp4
  ```
- **If narration is longer than the clip**, extend the clip instead of truncating
  the voice: `tpad=stop_mode=clone:stop_duration=<seconds>` freezes the last frame
  to fill the gap, then apply the `adelay`+`apad` merge above.
- Symptom of getting this wrong across a multi-clip concat: progressive audio
  drift, where each subsequent clip's narration starts earlier/later than it
  should — ffmpeg's concat demuxer picks up a clip's audio where the *previous
  clip's audio track* ended, not where its video ended, so any short audio track
  compounds the drift on every clip after it.

`build_video.py` in this skill sidesteps the truncation risk a different way: it
extends the frame-hold list itself (see the `durs[-1] += ...` line) so the video
segment is already ≈ narration length *before* muxing, then uses `apad` + a final
`-shortest` only as a belt-and-braces trim once durations are already reconciled.
If you're wiring up a merge step from scratch (a single ad-hoc beat, or a
different pipeline), prefer the explicit `adelay`+`apad=whole_dur`+`tpad` pattern
above — it doesn't depend on pre-computing frame durations to stay safe.

## Iterating cheaply on one beat

Re-rendering the whole video for a one-line narration tweak is slow and re-encodes
footage that didn't change. Three options, cheapest first:

1. **Splice** — rebuild only the target beat's clip, then cut it into the already
   assembled output: extract the segment *before* the beat and the segment *after*
   it from the existing final MP4 with `-ss`/`-to` + stream copy (`-c copy`, no
   re-encode), then concat `before + new-beat + after`. Requires knowing each
   beat's offset in the final file — keep a small sidecar (e.g. cumulative beat
   durations) alongside the output so you don't have to re-derive it.
2. **Recompute + re-concat** — `build_video.py` already writes one `<label>.mp4`
   per beat into `<REC>/build/` before concatenating them. If those cached clips
   are still around, rebuild just the changed beat's clip and re-run the final
   concat over the full set. Cheaper than a full rebuild because only one beat
   re-runs TTS + frame assembly; the concat itself is a stream copy.
3. **Full rebuild** — reprocess every beat from scratch. Reserve this for the
   initial assembly, or when the recording/timeline itself changed (re-recorded
   steps, new frames) — in that case the cached per-beat clips are stale anyway
   and splicing/recompute would just propagate the staleness.

Prefer 1 or 2 whenever only narration text or a single beat's timing changed;
only fall back to 3 for structural changes to the recording.

## 6. Verify before delivering

Extract and LOOK at key frames — the last frame of each beat window and the final frame:

```bash
ffmpeg -ss <t> -i out.mp4 -frames:v 1 -q:v 3 /tmp/check.jpg
```

Confirm: interactions visible (typing mid-flight, cursor on buttons), no spinner in
closing frames, result/card states rendered. If a beat looks wrong, fix steps/beats and
re-record — recordings are cheap.

## Workflow summary

1. Launch CDP Chrome → user SSOs once.
2. `cdpeval.py`/`drive.py` to map the flow and validate markers (dry-run).
3. Write `steps_*.json` (labels = beat boundaries) + `beats_*.json` (narration).
4. `screencast.py` per video → check key frames.
5. `build_video.py` per video → `assemble_full.py` → final MP4.
