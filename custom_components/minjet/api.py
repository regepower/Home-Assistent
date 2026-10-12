"""Async client for the Minjet cloud (REST)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
import logging
from typing import Any

import aiohttp

from .const import BASE_URL, WRITABLE_KEYS

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)

# The cloud sends naive timestamps in China standard time (UTC+8, no DST).
SERVER_TZ = timezone(timedelta(hours=8))


class MinjetError(Exception):
    """Base error for the Minjet API."""


class MinjetAuthError(MinjetError):
    """Login failed or the token was rejected."""


class MinjetConnectionError(MinjetError):
    """The cloud could not be reached or returned something unexpected."""


class MinjetApi:
    """Thin client around the endpoints used by the Minjet app."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        base_url: str = BASE_URL,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._username = username
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._token: str | None = None

    async def async_login(self) -> None:
        """Log in and store the bearer token."""
        data = await self._raw_request(
            "POST",
            "login",
            json_body={"username": self._username, "password": self._password},
            auth=False,
        )
        token = data.get("token")
        if data.get("code") != 200 or not token:
            raise MinjetAuthError(str(data.get("msg") or "login failed"))
        self._token = token

    async def async_get_devices(self) -> dict[str, dict[str, Any]]:
        """Return all bound devices keyed by serial number."""
        data = await self._request("GET", "device/queryUserDeviceList")
        devices = data.get("data")
        if not isinstance(devices, list):
            raise MinjetConnectionError("unexpected device list response")
        return {
            device["serialNum"]: device
            for device in devices
            if isinstance(device, dict) and device.get("serialNum")
        }

    async def async_get_notices(self) -> dict[str, dict[str, Any]]:
        """Return the latest warning message per device, keyed by serial number."""
        data = await self._request("GET", "app/notice/queryAppNoticeList")
        devices = (data.get("data") or {}).get("deviceList")
        if not isinstance(devices, list):
            raise MinjetConnectionError("unexpected notice list response")
        notices: dict[str, dict[str, Any]] = {}
        for item in devices:
            if not isinstance(item, dict) or not item.get("serialNum"):
                continue
            last = item.get("lastMessage") or {}
            notices[item["serialNum"]] = {
                "message": last.get("text"),
                "title": last.get("title"),
                "time": parse_server_time(last.get("time")),
            }
        return notices

    async def async_set_property(self, serial: str, key: str, value: int) -> None:
        """Write one device property (balcony storage: setRatedPower endpoint)."""
        if key not in WRITABLE_KEYS:
            raise ValueError(f"{key} is not a writable property")
        data = await self._request(
            "POST",
            f"photovoltaic/setRatedPower/{serial}",
            json_body={"key": key, "value": value},
        )
        if data.get("code") != 200:
            raise MinjetConnectionError(str(data.get("msg") or "write rejected"))

    async def _request(
        self, method: str, path: str, *, json_body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Call an authenticated endpoint, logging in again once if needed."""
        for attempt in (1, 2):
            if self._token is None:
                await self.async_login()
            try:
                return await self._raw_request(method, path, json_body=json_body)
            except MinjetAuthError:
                self._token = None
                if attempt == 2:
                    raise
        raise MinjetAuthError("authentication failed")  # pragma: no cover

    async def _raw_request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            async with self._session.request(
                method,
                f"{self._base_url}/{path}",
                json=json_body,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise MinjetAuthError("token rejected")
                if resp.status != 200:
                    raise MinjetConnectionError(f"HTTP {resp.status}")
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise MinjetConnectionError(str(err) or type(err).__name__) from err
        if not isinstance(data, dict):
            raise MinjetConnectionError("unexpected response")
        if auth and data.get("code") == 401:
            raise MinjetAuthError(str(data.get("msg") or "token rejected"))
        return data


def parse_server_time(value: Any) -> datetime | None:
    """Convert a naive cloud timestamp (UTC+8) to an aware UTC datetime."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
    except ValueError:
        return None
    return parsed.replace(tzinfo=SERVER_TZ).astimezone(UTC)
