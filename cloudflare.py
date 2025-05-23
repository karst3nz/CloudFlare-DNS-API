
from __future__ import annotations
import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple
import aiohttp
from log import create_logger  # Project logger factory

BASE_URL = "https://api.cloudflare.com/client/v4/"


class CloudflareAsyncAPI:
    """Asynchronous Cloudflare REST v4 client (Bearer token / Global API Key)."""

    # ---------------- Factories ---------------- #
    @classmethod
    def from_api_token(cls, token: str, *, timeout: int = 10, verify_token_on_enter: bool = True):
        return cls(token=token, timeout=timeout, verify_token_on_enter=verify_token_on_enter)

    @classmethod
    def from_global_key(cls, email: str, api_key: str, *, timeout: int = 10):
        return cls(global_email=email, global_key=api_key, timeout=timeout, verify_token_on_enter=True)

    # ---------------- init ------------------- #
    def __init__(self, *, token: str | None = None, global_email: str | None = None, global_key: str | None = None,
                 timeout: int = 10, verify_token_on_enter: bool = True, msg2edit: bool = True):
        # Logger is now unique for each instance
        self._logger = create_logger(__name__, "CloudFlare-API")
        if token and (global_email or global_key):
            raise ValueError("Specify either token or global_key, not both")
        if not token and not (global_email and global_key):
            raise ValueError("Need either token= or email+global_key pair")
        self._auth_type = "token" if token else "global"
        self._token = token
        self._g_email = global_email
        self._g_key = global_key
        self._timeout_cfg = aiohttp.ClientTimeout(total=timeout)
        self._verify_on_enter = verify_token_on_enter
        self._session: Optional[aiohttp.ClientSession] = None
        self._cached_account_id: Optional[str] = None

    # ------------ Exceptions ------------ #
    @staticmethod
    class ZoneAlreadyExists(RuntimeError):
        """Attempt to create a zone that already exists in the account."""
    @staticmethod
    class InvalidRequestHeaders(RuntimeError):
        """Code 6003 / 6111 — invalid request headers."""
    @staticmethod
    class IdenticalRecoedExists(RuntimeError):
        """Code 81058"""
    @staticmethod
    class DNSRecordInvalid(RuntimeError):
        """Code 9002"""
    @staticmethod
    class UserCredsInvalid(RuntimeError):
        """"""
    @staticmethod
    class ExceededZonesLimit(RuntimeError):
        """Code 1118"""

    # ---------------- context ------------ #
    async def __aenter__(self):
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self._auth_type == "token":
            headers["Authorization"] = f"Bearer {self._token}"
        else:
            headers.update({"X-Auth-Email": self._g_email or "", "X-Auth-Key": self._g_key or ""})
        self._session = aiohttp.ClientSession(headers=headers, timeout=self._timeout_cfg)
        self._logger.info("HTTP session opened (auth=%s)", self._auth_type)
        if self._verify_on_enter:
            await self._verify_auth()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session and not self._session.closed:
            await self._session.close()
            self._logger.info("HTTP session closed")

    # ---------------- low-level ------------- #
    async def _request(self, method: str, path: str, *, expect_success: bool = True, **kwargs):
        if not self._session:
            raise RuntimeError("Session not started")
        url = f"{BASE_URL}{path.lstrip('/')}"
        self._logger.debug("→ %s %s", method.upper(), url)
        async with self._session.request(method, url, **kwargs) as resp:
            data: Dict[str, Any] = await resp.json(content_type=None)
            self._logger.debug("← HTTP %s JSON: %s", resp.status, data)
            if expect_success and not data.get("success", False):
                for err in data.get("errors", []):
                    code = err.get("code")
                    if code in (1061, 10006):
                        raise self.ZoneAlreadyExists(err.get("message", "Zone already exists"))
                    if code in (6003, 6103) or any(chain.get("code") == 6111 for chain in err.get("error_chain") or []):
                        raise self.InvalidRequestHeaders(err.get("message", "Invalid request headers"))
                    if code == 81058:
                        raise self.IdenticalRecoedExists(err.get("message", "An identical record already exists."))
                    if code == 9002:
                        raise self.DNSRecordInvalid(err.get("message", "DNS record type is invalid."))
                    if code == 1118:
                        raise self.ExceededZonesLimit(err.get("message", "Account has exceeded the limit for adding zones"))
                raise RuntimeError(f"Cloudflare error: {data.get('errors')}")
            return data.get("result", data)

    async def _verify_auth(self):
        if self._auth_type == "token":
            res = await self._request("GET", "user/tokens/verify", expect_success=False)
            self._logger.info("API token is valid (user=%s)", res.get("result", {}).get("id"))
        else:
            user = await self._request("GET", "user", expect_success=False)
            if user is None: raise self.UserCredsInvalid("Email or GlobalKey are invalid")
            self._logger.info("Global API Key is valid (user=%s)", user.get("id"))

    # ---------- helpers ---------- #
    async def _default_account_id(self) -> Optional[str]:
        if self._cached_account_id:
            return self._cached_account_id
        user = await self._request("GET", "user", expect_success=False)
        if user is None: raise self.UserCredsInvalid("Email or GlobalKey are invalid")
        acc_id = None
        if user.get("account"):
            acc_id = user["account"].get("id")
        elif user.get("accounts"):
            acc_id = user["accounts"][0]["id"]
        else:
            accounts = await self._request("GET", "accounts")
            if accounts:
                acc_id = accounts[0]["id"]
        self._cached_account_id = acc_id
        return acc_id

    # ---------- zones ------------ #
    async def create_zone(self, name: str, *, jump_start: bool = False, zone_type: str = "full"):
        payload: Dict[str, Any] = {"name": name, "jump_start": jump_start, "type": zone_type}
        if (acc_id := await self._default_account_id()):
            payload["account"] = {"id": acc_id}
        self._logger.info("Creating zone {}…".format(name))
        return await self._request("POST", "zones", json=payload)

    async def register_domain(self, name: str, *, fail_if_exists: bool = False, **kwargs) -> Tuple[str, str, str]:
        try:
            zone = await self.create_zone(name, **kwargs)
        except self.ZoneAlreadyExists:
            if fail_if_exists:
                raise
            self._logger.info("Zone {} already exists — retrieving ID".format(name))
            zone = (await self._request("GET", "zones", params={"name": name}))[0]
        ns = zone.get("name_servers", [])
        if len(ns) < 2:
            raise RuntimeError("Cloudflare did not return two NS servers")
        return zone["id"], ns[0], ns[1]

    # ---------- DNS --------------- #
    async def add_dns_record(self, zone_id: str, record_type: str, name: str, content: str, *, ttl: int = 1, **extra):
        payload = {"type": record_type.upper(), "name": name, "content": content, "ttl": ttl, **extra}
        self._logger.info("Adding record {} {} → {}".format(record_type.upper(), name, content))
        return await self._request("POST", f"zones/{zone_id}/dns_records", json=payload)

    # ---------- status ------------ #
    async def zone_status(self, zone_id: str) -> str:
        return (await self._request("GET", f"zones/{zone_id}"))["status"]

    async def wait_until_active(self, zone_id: str, *, interval: int = 15, timeout: int = 1800):
        self._logger.info("Waiting for zone {} to become active".format(zone_id))
        start = time.monotonic()
        while True:
            if await self.zone_status(zone_id) == "active":
                self._logger.info("Zone {} is active".format(zone_id))
                return
            if time.monotonic() - start > timeout:
                raise TimeoutError("Zone activation timed out")
            await asyncio.sleep(interval)

