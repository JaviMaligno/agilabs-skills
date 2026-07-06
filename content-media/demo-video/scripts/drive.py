#!/usr/bin/env python3
"""Drive the page through steps via CDP WITHOUT recording (dry-run / probe).

Injects the same naturalness helpers as screencast.py (helpers.js) so step files are
interchangeable between dry-runs and recordings. Prints the page innerText at the end.
Also disables the HTTP cache (safe here — no screencast competing for the websocket)
so a dry-run picks up a freshly deployed frontend bundle.

Usage: drive.py <page_ws_url> <script_json>
Steps: same as screencast.py: {"eval"}, {"sleep"}, {"waitjs"}, {"setfiles"}, {"navigate"}.
"""
import sys, json, asyncio, os, time
import websockets

WS = sys.argv[1]
STEPS = json.load(open(sys.argv[2]))
HELPERS_JS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpers.js")).read()

_id = 0
def nid():
    global _id; _id += 1; return _id

async def main():
    async with websockets.connect(WS, max_size=None) as ws:
        pending = {}
        async def call(method, params=None):
            i = nid()
            fut = asyncio.get_event_loop().create_future()
            pending[i] = fut
            await ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
            return await asyncio.wait_for(fut, timeout=180)
        async def reader():
            async for raw in ws:
                msg = json.loads(raw)
                if "id" in msg and msg["id"] in pending:
                    pending.pop(msg["id"]).set_result(msg.get("result"))
        rtask = asyncio.create_task(reader())
        await call("Runtime.enable"); await call("DOM.enable")
        try:
            await call("Network.enable")
            await call("Network.setCacheDisabled", {"cacheDisabled": True})
        except Exception:
            pass
        async def ev(js):
            return await call("Runtime.evaluate", {"expression": js, "returnByValue": True, "awaitPromise": True})
        await ev(HELPERS_JS)
        for step in STEPS:
            if "navigate" in step:
                await call("Page.enable")
                await call("Page.navigate", {"url": step["navigate"]})
                await asyncio.sleep(3)
                await ev(HELPERS_JS)
            elif "eval" in step:
                await ev(step["eval"])
            elif "setfiles" in step:
                doc = await call("DOM.getDocument", {"depth": 1})
                node = await call("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": step.get("selector", "input[type=file]")})
                if node.get("nodeId"):
                    await call("DOM.setFileInputFiles", {"files": [step["setfiles"]], "nodeId": node["nodeId"]})
            elif "sleep" in step:
                await asyncio.sleep(step["sleep"])
            elif "waitjs" in step:
                deadline = time.time() + step.get("timeout", 25)
                while time.time() < deadline:
                    r = await ev(step["waitjs"])
                    if r and r.get("result", {}).get("value") is True:
                        break
                    await asyncio.sleep(step.get("poll", 2.0))
        r = await ev("(document.body.innerText||'').replace(/\\n{2,}/g,'\\n')")
        print(r.get("result", {}).get("value", ""))
        rtask.cancel()

asyncio.run(main())
