import aiohttp
from aiohttp import ClientSession, ClientWebSocketResponse
import asyncio
import json
import signal


async def run():
    async with ClientSession() as session:
        async with session.ws_connect("http://aca-py:8021/ws", autoping=False) as ws:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(ws)))
            async for msg in ws:
                print(msg)


async def shutdown(ws: ClientWebSocketResponse):
    try:
        await ws.close()
    finally:
        loop = asyncio.get_event_loop()
        print("cancelling tasks")
        [
            task.cancel()
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
        ]
        print("stopping event loop")
        loop.stop()


async def test_ws(url: str = "https://agents.labor.gematik.de:8041/ws"):
    import functools
    import logging
    from ws_client import WSClient

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s :: %(message)s",
    )

    async def shutdown(
        ws_client: WSClient,
    ):
        logging.debug("shutdown called")
        logging.debug("stopping ws client")
        await ws_client.stop()

    async with aiohttp.ClientSession(
        auth=aiohttp.BasicAuth("mobctrl", "p8vgIJPvWCgUWk0Bicdu")
    ) as session:
        ws_client = WSClient(url, session)
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(
            signal.SIGINT,
            # functools.partial(loop.create_task, shutdown(ws_client)),
            lambda: loop.create_task(shutdown(ws_client)),
        )
        logging.info("creating ws task")
        await ws_client.run()


# def get_filter_for_state(state):
#     return lambda msg: msg.get("payload").get("state") == state

# results = await asyncio.gather(
#     *[
#         ws_client.wait_for_event(topic, filter)
#         for topic, filter in (
#             (
#                 "out_of_band",
#                 get_filter_for_state("await-response"),
#             ),
#             (
#                 "connections",
#                 get_filter_for_state("invitation"),
#             ),
#         )
#     ]
# )
# logging.info("results:\n%s", "\n".join([json.dumps(r) for r in results]))
# logging.info("adding task done callback")
# task.add_done_callback(lambda task: logging.info("task %s completed!", task))
# # ... wait ...
# logging.info("sleeping")
# await asyncio.sleep(5)
# logging.info("waking up")
# logging.info("stopping ws client")
# await ws_client.stop()
# logging.info("waiting for task to end")
# await asyncio.wait_for(task, .01)
# logging.info("success!")


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else None
    # asyncio.run(test_ws(url))
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(test_ws(url))
    finally:
        print("closing async generators")
        loop.run_until_complete(loop.shutdown_asyncgens())
        print("asyncgens have been shut down")
        print("closing event loop")
        loop.close()
        print("event loop closed")
