"""Async client for the Minjet cloud (REST + WebSocket)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import json
import logging
from typing import Any

import aiohttp

from .const import BASE_URL, WRITABLE_KEYS, WS_RECEIVE_TIMEOUT, WS_URL

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)


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
        ws_url: str = WS_URL,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._username = username
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._ws_url = ws_url
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

    async def async_run_websocket(
        self, on_device: Callable[[dict[str, Any]], Awaitable[None] | None]
    ) -> None:
        """Stream device updates until the connection ends.

        Returns when the server closes the connection or stays silent too long;
        the caller is expected to reconnect.
        """
        if self._token is None:
            await self.async_login()
        try:
            async with self._session.ws_connect(
                f"{self._ws_url}?token={self._token}",
                heartbeat=30,
                timeout=aiohttp.ClientWSTimeout(ws_receive=WS_RECEIVE_TIMEOUT),
            ) as ws:
                async for message in ws:
                    if message.type is not aiohttp.WSMsgType.TEXT:
                        if message.type in (
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.CLOSING,
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break
                        continue
                    device = _parse_ws_message(message.data)
                    if device is not None:
                        result = on_device(device)
                        if result is not None:
                            await result
        except aiohttp.WSServerHandshakeError as err:
            if err.status in (401, 403):
                self._token = None
                raise MinjetAuthError("websocket rejected the token") from err
            raise MinjetConnectionError("websocket handshake failed") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise MinjetConnectionError("websocket connection lost") from err

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


def _parse_ws_message(raw: str) -> dict[str, Any] | None:
    """Return the device object of a ``detail`` push message, else None."""
    try:
        payload = json.loads(raw)
    except ValueError:
        _LOGGER.debug("Ignoring non-JSON websocket message")
        return None
    if not isinstance(payload, dict) or payload.get("type") != "detail":
        return None
    device = payload.get("data")
    if isinstance(device, dict) and device.get("serialNum"):
        return device
    return None
