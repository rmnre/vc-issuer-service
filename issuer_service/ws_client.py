"""WS Client implementation."""

import asyncio
import logging
from json import JSONDecodeError
from typing import Callable, Coroutine, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class WSClient:
    """WS Client."""

    def __init__(self, ws_endpoint: str, session: aiohttp.ClientSession):
        self.topics_to_processors: dict[str, List[Callable[[dict], Coroutine]]] = {}
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.ws_endpoint = ws_endpoint
        self.session = session

    async def start(self):
        loop = asyncio.get_event_loop()
        task = loop.create_task(self.run())
        return task

    async def run(self, max_attempts: int = 5, retry_interval: float = 3):
        max_attempts = abs(max_attempts)
        delay = retry_interval
        for attempt in range(1, max_attempts + 1):
            try:
                async with self.session.ws_connect(
                    self.ws_endpoint, autoping=False
                ) as ws:
                    logger.info("websocket connected")
                    self.ws = ws
                    await self.listen()
                    return
            except aiohttp.ClientConnectorError:
                error_msg = (
                    "error when connecting to %(url)s (attempt %(at)d of %(maxat)d)"
                )
                if attempt < max_attempts:
                    error_msg = f"{error_msg} - retrying in %(retry).2fs..."
                else:
                    delay = 0
                logger.error(
                    error_msg,
                    {
                        "url": self.ws_endpoint,
                        "at": attempt,
                        "maxat": max_attempts,
                        "retry": retry_interval,
                    },
                )
                await asyncio.sleep(delay)

        logger.critical("all connection attempts failed")

    async def listen(self):
        logger.debug("starting to listen for ws messages")
        async for msg in self.ws:
            logger.debug("received message with payload: %s", msg.data)
            await self.handle_msg(msg)
        logger.debug("stopped listening")

    async def handle_msg(self, msg: aiohttp.WSMessage):
        if msg.type is not aiohttp.WSMsgType.TEXT:
            return

        try:
            payload = msg.json()
            if "topic" in payload:
                await self.notify_subscribers(payload["topic"], payload)
        except JSONDecodeError:
            logger.exception("msg is not valid json")

    async def notify_subscribers(self, topic: str, msg: dict):
        for top, processors in self.topics_to_processors.items():
            if top == topic:
                # TODO: remove async? else: schedule without await?
                for processor in processors:
                    try:
                        await processor(msg)
                    except Exception:
                        logger.exception(
                            "Error while processing event. Processor: %s", processor
                        )

                break

    def subscribe(self, topic: str, processor: Callable[[dict], Coroutine]):
        if topic not in self.topics_to_processors:
            self.topics_to_processors[topic] = []
        self.topics_to_processors[topic].append(processor)

    def unsubscribe(self, topic: str, processor: Callable[[dict], Coroutine]):
        if topic in self.topics_to_processors:
            try:
                index = self.topics_to_processors[topic].index(processor)
            except ValueError:
                return
            del self.topics_to_processors[topic][index]
            if not self.topics_to_processors[topic]:
                del self.topics_to_processors[topic]
            logger.debug("Unsubscribed: topic %s, processor %s", topic, processor)

    async def wait_for_event(
        self, topic: str, filter_: Callable[[dict], bool] = None, timeout: float = None
    ) -> dict:
        """
        Wait for event of specified topic.
        :param topic: event topic
        :param filter_: event filter
        :param timeout: timeout
        :return: event payload
        :raises asyncio.TimeoutError: on timeout

        """
        future = asyncio.get_event_loop().create_future()

        async def _handle_event(msg: dict):
            if filter_ and not filter_(msg):
                return
            future.set_result(msg)
            self.unsubscribe(topic, _handle_event)

        self.subscribe(topic, _handle_event)
        logger.debug("waiting for event with topic '%s'", topic)
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self.unsubscribe(topic, _handle_event)
            raise

        return result

    async def stop(self):
        if self.ws and not self.ws.closed:
            logger.debug("Closing websocket...")
            await self.ws.close()
            logger.debug("Websocket closed.")
