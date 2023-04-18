import asyncio
import logging

from datetime import datetime, timezone
from typing import List, Optional

import aiohttp

from .ws_client import WSClient

logger = logging.getLogger(__name__)

OOB_CREATE_REQUEST_TEMPLATE = {
    "accept": ["didcomm/aip1", "didcomm/aip2;env=rfc19"],
    "handshake_protocols": ["https://didcomm.org/didexchange/1.0"],
    "my_label": "Nextcloud Credential Issuer",
    "protocol_version": "1.1",
}


def conn_completed_filter(event: dict, connection_id: str):
    conn_record: dict = event.get("payload", False)
    return (
        conn_record
        and conn_record["connection_id"] == connection_id
        and conn_record["state"] == "completed"
    )


def issuance_done_or_abandoned_filter(event: dict, cred_ex_id: str):
    cred_ex_record: dict = event.get("payload", False)
    return (
        cred_ex_record
        and cred_ex_record["cred_ex_id"] == cred_ex_id
        and cred_ex_record["state"] in ("done", "abandoned")
    )


class Controller:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        ws_client: WSClient,
        did_seed: str = None,
        issuance_timeout: float = None,
        auto_remove_conn_record: bool = None,
        loop: asyncio.AbstractEventLoop = None,
    ):
        self.session = session
        self.ws_client = ws_client
        self.did_seed = did_seed
        self.issuance_timeout = issuance_timeout
        self.auto_remove_conn_record = auto_remove_conn_record
        self.loop = loop
        self.did = None

    async def start(self):
        if not self.loop:
            self.loop = asyncio.get_event_loop()
        await self.ws_client.start()
        # wait until aca-py is ready
        logger.debug("waiting for message from aca-py...")
        await self.ws_client.wait_for_event("settings")
        # create issuer did
        self.did = await self.create_did(seed=self.did_seed)

    async def create_did(
        self, method: str = "key", key_type: str = "bls12381g2", seed: str = None
    ):
        logger.debug("creating did...")
        request = {
            "method": method,
            "options": {"key_type": key_type},
        }
        if seed:
            request["seed"] = seed
        async with self.session.post("/wallet/did/create", json=request) as resp:
            resp.raise_for_status()
            body = await resp.json()
        did: str = body["result"]["did"]
        logger.info("created did %s", did)
        return did

    async def issue_nextcloud_credential(
        self,
        connection_id: str,
        firstname: str,
        lastname: str,
        email: str,
        issuance_date: str = None,
        timeout: float = None,
        auto_remove_conn_record: bool = None,
    ):
        credential = Controller.make_nextcloud_credential(
            firstname, lastname, email, self.did, issuance_date
        )
        asyncio.create_task(
            self.issue_credential_when_connection_completed(
                connection_id, credential, timeout, auto_remove_conn_record
            )
        )

    async def issue_credential_when_connection_completed(
        self,
        conn_id: str,
        credential: dict,
        timeout: float = None,
        auto_remove_conn_record: bool = None,
    ):
        timeout = timeout or self.issuance_timeout
        auto_remove_conn_record = bool(
            auto_remove_conn_record or self.auto_remove_conn_record
        )
        error = None
        try:
            await self.ws_client.wait_for_event(
                "connections",
                lambda ev: conn_completed_filter(ev, conn_id),
                timeout,
            )
            cred_ex_record = await self.auto_issue_credential(conn_id, credential)
        except asyncio.TimeoutError as err:
            error = err
            logger.warning("Timeout during credential issuance.")
        except aiohttp.ClientResponseError as err:
            error = err
            logger.error(
                "Credential issuance failed. Agent response: %s (%s)",
                err.message,
                err.status,
            )

        if auto_remove_conn_record:
            try:
                if not error:
                    try:
                        await self.ws_client.wait_for_event(
                            "issue_credential_v2_0",
                            lambda ev: issuance_done_or_abandoned_filter(
                                ev, cred_ex_record["cred_ex_id"]
                            ),
                            timeout,
                        )
                    except asyncio.TimeoutError:
                        # timeout -> delete conn record
                        pass
                await self.delete_record("connections", conn_id)
                logger.info("connection record removed")
            except aiohttp.ClientResponseError:
                logger.error("could not remove connection record %s", conn_id)

    async def auto_issue_credential(self, conn_id, credential) -> dict:
        issue_request = Controller.make_issue_request(conn_id, credential)
        async with self.session.post(
            "/issue-credential-2.0/send", json=issue_request
        ) as resp:
            resp.raise_for_status()
            cred_ex_record = await resp.json()
        return cred_ex_record

    async def create_oob_invitation(self, alias: str, my_label: str = None):
        async with self.session.post(
            "/out-of-band/create-invitation",
            json=Controller.make_oob_create_request(alias),
        ) as resp:
            resp.raise_for_status()
            invitation_record: dict = await resp.json()
        return invitation_record

    async def query_connections(
        self, invitation_msg_id: str = None, state: str = None, **kwargs
    ) -> List[Optional[dict]]:
        params = kwargs
        if invitation_msg_id:
            params["invitation_msg_id"] = invitation_msg_id
        if state:
            params["state"] = state

        async with self.session.get("/connections", params=params) as resp:
            resp.raise_for_status()
            results_obj = await resp.json()

        return results_obj["results"]

    async def delete_record(self, protocol: str, record_id: str):
        async with self.session.delete(f"/{protocol}/{record_id}") as resp:
            resp.raise_for_status()

    @staticmethod
    def make_oob_create_request(alias: str):
        request = OOB_CREATE_REQUEST_TEMPLATE.copy()
        request["alias"] = alias
        return request

    @staticmethod
    def make_nextcloud_credential(
        firstname: str,
        lastname: str,
        email: str,
        issuer_did: str,
        issuance_date: str = None,
    ):
        if not issuance_date:
            issuance_date = (
                datetime.utcnow()
                .replace(tzinfo=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )

        return {
            "@context": [
                "https://www.w3.org/2018/credentials/v1",
                "https://agents.labor.gematik.de/credential/nextcloudCredential",
                "https://w3id.org/security/bbs/v1",
            ],
            "type": ["VerifiableCredential", "NextcloudCredential"],
            "credentialSubject": {
                "givenName": firstname,
                "familyName": lastname,
                "email": email,
            },
            "issuer": issuer_did,
            "issuanceDate": issuance_date,  # ex: "2023-03-17T14:56:53.111049600Z"
        }

    @staticmethod
    def make_issue_request(
        conn_id: str, credential: dict, proof_type: str = "BbsBlsSignature2020"
    ):
        return {
            "connection_id": conn_id,
            "filter": {
                "ld_proof": {
                    "credential": credential,
                    "options": {"proofType": proof_type},
                }
            },
        }
