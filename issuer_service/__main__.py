import asyncio
import logging
import signal

import aiohttp

from configargparse import Namespace

from .controller import Controller
from .log import configure_logger
from .parse import init_argparser
from .webapp import Webapp
from .ws_client import WSClient

logger = logging.getLogger(__name__)


async def run(args: Namespace):
    session = aiohttp.ClientSession(base_url=args.agent_admin_api)
    ws_client = WSClient("/ws", session)
    controller = Controller(
        session,
        ws_client,
        args.did_seed,
        args.issuance_timeout,
        args.auto_remove_conn_record,
    )
    webapp = Webapp()

    async def shutdown(timeout: float = None):
        async def stop_services():
            await webapp.stop()
            await ws_client.stop()

        logger.debug("stopping services (timeout: %ds)", timeout)
        try:
            await asyncio.wait_for(stop_services(), timeout)
        except asyncio.TimeoutError:
            logger.error("timeout while stopping services")

        logger.debug("closing client session")
        await session.close()
        logger.debug("cancelling remaining tasks")
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task():
                task.cancel()

        logger.debug("stopping event loop")
        loop.stop()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(3)))

    await webapp.setup(
        args.host, args.port, args.agent_admin_api, controller, args.oob_base_url
    )

    # run app and ws client
    await webapp.start(session)
    # await ws_client.start()
    await controller.start()


def main():
    # read command line args
    parser = init_argparser()
    args = parser.parse_args()
    configure_logger(args.log_level, args.log_config)

    loop = asyncio.new_event_loop()
    try:
        loop.create_task(run(args))
        loop.run_forever()
    except asyncio.CancelledError:
        logger.error("event loop was cancelled")
    finally:
        logger.debug("shutting down asyncgens")
        loop.run_until_complete(loop.shutdown_asyncgens())
        logger.debug("closing event loop")
        loop.close()

    logger.info("service stopped")


main()
