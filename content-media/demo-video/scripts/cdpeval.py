#!/usr/bin/env python3
"""One-shot CDP eval helper: cdpeval.py <page_ws> <js-expression>
Evaluates the JS in the page (awaiting promises) and prints the JSON result."""
import sys, json, asyncio, websockets

WS = sys.argv[1]; JS = sys.argv[2]

async def main():
    async with websockets.connect(WS, max_size=None) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
        await ws.recv()
        await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate",
                                  "params": {"expression": JS, "returnByValue": True, "awaitPromise": True}}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 2:
                r = msg.get("result", {})
                if "exceptionDetails" in r:
                    print("EXCEPTION:", json.dumps(r["exceptionDetails"].get("exception", {}).get("description", r["exceptionDetails"]))[:300])
                else:
                    print(json.dumps(r.get("result", {}).get("value")))
                return

asyncio.run(main())
