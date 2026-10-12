"""Tests for the Minjet API client."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.minjet.api import (
    MinjetApi,
    MinjetAuthError,
    MinjetConnectionError,
)
from custom_components.minjet.const import BASE_URL

from .conftest import PASSWORD, SERIAL, USERNAME


async def test_login_and_devices(
    hass: HomeAssistant, mock_cloud: AiohttpClientMocker
) -> None:
    """Login stores the token and the device list is keyed by serial."""
    api = MinjetApi(async_get_clientsession(hass), USERNAME, PASSWORD)
    devices = await api.async_get_devices()
    assert list(devices) == [SERIAL]
    login_call = mock_cloud.mock_calls[0]
    assert login_call[2] == {"username": USERNAME, "password": PASSWORD}
    assert mock_cloud.mock_calls[1][3]["Authorization"] == "Bearer tok"


async def test_login_rejected(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A non-200 body code on login is an auth error."""
    aioclient_mock.post(f"{BASE_URL}/login", json={"code": 500, "msg": "bad password"})
    api = MinjetApi(async_get_clientsession(hass), USERNAME, "wrong")
    with pytest.raises(MinjetAuthError):
        await api.async_login()


async def test_expired_token_triggers_relogin(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    device: dict[str, Any],
) -> None:
    """A 401 body code on a data call logs in again and retries once."""
    aioclient_mock.post(f"{BASE_URL}/login", json={"code": 200, "token": "tok"})
    responses = [
        {"code": 401, "msg": "expired"},
        {"code": 200, "data": [device]},
    ]

    async def handler(method: str, url: Any, data: Any) -> AiohttpClientMockResponse:
        return AiohttpClientMockResponse(method, url, json=responses.pop(0))

    aioclient_mock.get(f"{BASE_URL}/device/queryUserDeviceList", side_effect=handler)
    api = MinjetApi(async_get_clientsession(hass), USERNAME, PASSWORD)
    assert list(await api.async_get_devices()) == [SERIAL]
    assert len([c for c in aioclient_mock.mock_calls if c[0] == "POST"]) == 2


async def test_unexpected_payload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A device list that is not a list raises a connection error."""
    aioclient_mock.post(f"{BASE_URL}/login", json={"code": 200, "token": "tok"})
    aioclient_mock.get(
        f"{BASE_URL}/device/queryUserDeviceList", json={"code": 200, "data": None}
    )
    api = MinjetApi(async_get_clientsession(hass), USERNAME, PASSWORD)
    with pytest.raises(MinjetConnectionError):
        await api.async_get_devices()
