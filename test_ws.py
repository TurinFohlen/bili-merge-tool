import asyncio
import websockets

async def test():
    async with websockets.connect("ws://127.0.0.1:8080") as ws:
        await ws.send("echo ok")
        response = await ws.recv()
        print(f"Response: {response!r}")

asyncio.run(test())
