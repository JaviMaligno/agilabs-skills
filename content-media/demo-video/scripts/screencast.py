#!/usr/bin/env python3
"""CDP screencast recorder + driver over a single websocket.

Records jpeg frames with timestamps while executing declarative steps that drive the
page. Auto-injects "naturalness" helpers so recordings look human:
  - window.__click('Button text' | 'css:selector')  -> glides a fake cursor (easing +
    drop shadow) to the element, shows a click ripple, then clicks. Returns a Promise.
  - window.__typeIn(el, text, cps)                  -> types char-by-char with a human
    rhythm into a React-controlled input/textarea (native value setter + input events).
  - window.__typeChat(text, cps)                    -> __typeIn on the chat textarea.
  - window.__moveTo(q), window.__findEl(q)          -> cursor motion / element lookup.
All helpers return Promises; steps are evaluated with awaitPromise so typing/motion
completes (and is captured frame-by-frame) before the next step runs.

Usage: screencast.py <page_ws_url> <out_frames_dir> <script_json>
Steps: {"eval":"..js.."} | {"navigate":"url"} | {"sleep":secs}
     | {"waitjs":"..js bool..","timeout":n,"poll":s}
     | {"setfiles":"/abs/path","selector":"input[type=file]"}   (CDP file upload)
Any step may carry {"label": "..."} — recorded into timeline.json for the beat builder.
Output: <dir>/NNNNN.jpg + frames.jsonl (frame timestamps) + timeline.json (step marks).

Gotchas (hard-won): do NOT enable Network.setCacheDisabled here (starves the ws and
the calls time out); record over an already-loaded page after a frontend deploy
(relaunch Chrome to pick the new bundle); waitjs polls >= 2s on long LLM turns.
"""
import sys, json, asyncio, base64, time, os
import websockets

WS = sys.argv[1]
OUT = sys.argv[2]
STEPS = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else [{"sleep": 6}]
os.makedirs(OUT, exist_ok=True)

# Naturalness helpers, injected once at start (and re-injected after navigate).
HELPERS_JS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpers.js")).read()

_id = 0
def nid():
    global _id; _id += 1; return _id

async def main():
    async with websockets.connect(WS, max_size=None) as ws:
        pending = {}
        frames_meta = []
        start = None

        async def call(method, params=None, timeout=180):
            i = nid()
            fut = asyncio.get_event_loop().create_future()
            pending[i] = fut
            await ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
            return await asyncio.wait_for(fut, timeout=timeout)

        async def reader():
            nonlocal start
            n = 0
            async for raw in ws:
                msg = json.loads(raw)
                if "id" in msg and msg["id"] in pending:
                    pending.pop(msg["id"]).set_result(msg.get("result"))
                elif msg.get("method") == "Page.screencastFrame":
                    p = msg["params"]
                    if start is None:
                        start = time.time()
                    t = time.time() - start
                    fn = os.path.join(OUT, f"{n:05d}.jpg")
                    with open(fn, "wb") as f:
                        f.write(base64.b64decode(p["data"]))
                    frames_meta.append({"i": n, "t": t})
                    n += 1
                    try:
                        await ws.send(json.dumps({"id": nid(), "method": "Page.screencastFrameAck",
                                                  "params": {"sessionId": p["sessionId"]}}))
                    except Exception:
                        pass

        rtask = asyncio.create_task(reader())
        await call("Page.enable")
        await call("Runtime.enable")
        await call("DOM.enable")
        # Render even when the window is backgrounded — without this a non-frontmost
        # tab emits ZERO screencast frames (renderer throttled).
        try:
            await call("Emulation.setFocusEmulationEnabled", {"enabled": True})
        except Exception:
            pass
        await call("Page.bringToFront")
        await call("Page.startScreencast", {"format": "jpeg", "quality": 70, "everyNthFrame": 2,
                                            "maxWidth": 1600, "maxHeight": 1000})

        async def run_eval(js):
            return await call("Runtime.evaluate", {"expression": js, "returnByValue": True, "awaitPromise": True})

        async def set_files(path, selector):
            doc = await call("DOM.getDocument", {"depth": 1})
            node = await call("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": selector})
            if not node or not node.get("nodeId"):
                print(f"WARN setfiles: selector not found: {selector}")
                return
            await call("DOM.setFileInputFiles", {"files": [path], "nodeId": node["nodeId"]})

        await run_eval(HELPERS_JS)

        timeline = []
        for _ in range(50):
            if start is not None:
                break
            await asyncio.sleep(0.1)
        for si, step in enumerate(STEPS):
            elapsed = (time.time() - start) if start else 0.0
            kind = next((k for k in ("navigate", "eval", "sleep", "waitjs", "setfiles") if k in step), "sleep")
            timeline.append({"step": si, "t": elapsed, "label": step.get("label", ""), "kind": kind})
            if "navigate" in step:
                await call("Page.navigate", {"url": step["navigate"]})
                await asyncio.sleep(3)
                await run_eval(HELPERS_JS)  # helpers are wiped by navigation
            elif "eval" in step:
                await run_eval(step["eval"])
            elif "setfiles" in step:
                await set_files(step["setfiles"], step.get("selector", "input[type=file]"))
            elif "sleep" in step:
                await asyncio.sleep(step["sleep"])
            elif "waitjs" in step:
                deadline = time.time() + step.get("timeout", 25)
                poll = step.get("poll", 2.0)
                while time.time() < deadline:
                    r = await run_eval(step["waitjs"])
                    if r and r.get("result", {}).get("value") is True:
                        break
                    await asyncio.sleep(poll)
        with open(os.path.join(OUT, "timeline.json"), "w") as f:
            json.dump(timeline, f)

        await call("Page.stopScreencast")
        await asyncio.sleep(0.3)
        rtask.cancel()
        with open(os.path.join(OUT, "frames.jsonl"), "w") as f:
            for m in frames_meta:
                f.write(json.dumps(m) + "\n")
        print(f"captured {len(frames_meta)} frames over {frames_meta[-1]['t']:.1f}s" if frames_meta else "NO FRAMES")

asyncio.run(main())
