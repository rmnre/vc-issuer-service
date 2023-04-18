import logging

import jinja2
import aiohttp_jinja2
from aiohttp import ClientSession, web

from .controller import Controller
from .presets import IMAGES_DIR, TEMPLATE_DIR
from .views import healthcheck, index, issue

logger = logging.getLogger(__name__)


class Webapp:
    async def setup(
        self,
        host: str,
        port: int,
        agent_admin_api: str,
        controller: Controller,
        oob_base_url: str = None,
    ):
        self.app = web.Application()
        aiohttp_jinja2.setup(self.app, loader=jinja2.FileSystemLoader(TEMPLATE_DIR))
        self.app["agent_admin_api"] = agent_admin_api
        self.app["oob_base_url"] = oob_base_url
        self.app["controller"] = controller
        self.app["n_requests"] = 0
        self.setup_routes()
        runner = web.AppRunner(self.app)
        await runner.setup()
        self.site = web.TCPSite(runner, host, port)

    async def start(self, session: ClientSession):
        self.app["client_session"] = session
        site = self.site
        await site.start()
        logger.info("=== server running on %s:%d ===", site._host, site._port)

    async def stop(self):
        logger.debug("shutting down webapp")
        await self.app.shutdown()
        logger.debug("cleaning up")
        await self.app.cleanup()
        logger.debug("done cleaning up")

    def setup_routes(self):
        self.app.add_routes(
            [
                web.get("/", index),
                web.post("/", issue),
                web.get("/health", healthcheck),
                web.static("/images", IMAGES_DIR),
            ]
        )
