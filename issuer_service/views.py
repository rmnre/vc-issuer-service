from base64 import b64encode
from io import BytesIO

import aiohttp
import aiohttp_jinja2
import qrcode

from aiohttp.web import Request, Response

from .controller import Controller


def make_qr_b64(payload: str):
    qr = qrcode.make(payload)
    buffered = BytesIO()
    qr.save(buffered)
    qr_b64 = b64encode(buffered.getvalue()).decode("utf-8")
    return qr_b64


@aiohttp_jinja2.template("index.jinja2")
async def index(request: Request):
    pass


@aiohttp_jinja2.template("invitation.jinja2")
async def issue(request: Request):
    # Flow:
    # 1) request data via form
    # 2) create & display oob invite -> "continue with wallet"
    # 3) wait for event connection complete
    # 4) create and send credential offer with auto_issue:true

    app = request.app
    requester_no = app["n_requests"] + 1
    app["n_requests"] = requester_no
    controller: Controller = app["controller"]
    form_data = await request.post()
    try:
        invitation_record = await controller.create_oob_invitation(
            f"requester #{requester_no}"
        )
        invitation_url: str = invitation_record["invitation_url"]
        invitation_msg_id = invitation_record["invi_msg_id"]

        conn_list = await controller.query_connections(
            invitation_msg_id=invitation_msg_id, state="invitation"
        )
        conn_record = conn_list[0]
        conn_id = conn_record["connection_id"]

        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # fix invitation url
        if app["oob_base_url"]:
            invitation_url = (
                f"{app['oob_base_url']}{invitation_url[invitation_url.find('?'):]}"
            )
        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

        qr_b64 = make_qr_b64(invitation_url)

        await controller.issue_nextcloud_credential(
            conn_id,
            form_data["firstName"],
            form_data["lastName"],
            form_data["email"],
        )

        return {
            "qr_b64": qr_b64,
            "invitation_url": invitation_url,
            "timeout": controller.issuance_timeout,
        }

    except aiohttp.ClientResponseError:
        raise aiohttp.web.HTTPServerError(reason="Could not obtain invitation record")


async def healthcheck(request: Request):
    return Response(text="OK")
