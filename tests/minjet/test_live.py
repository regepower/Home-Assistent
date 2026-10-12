"""Tests for the time-limited live mode (button + realtime WebSocket)."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import patch

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.minjet.api import MinjetApi
from custom_components.minjet.const import BASE_URL, DOMAIN

from .conftest import PASSWORD, SERIAL, USERNAME

DETAIL_URL = f"{BASE_URL}/photovoltaic/queryPhotovoltaic/{SERIAL}"
CLOSE_URL = f"{BASE_URL}/photovoltaic/closeRealTimeStatus/{SERIAL}"
SHORT = timedelta(seconds=0.2)


def _entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{SERIAL}_{key}"
    )
    assert entity_id is not None
    return entity_id


def _calls(mock: AiohttpClientMocker, url: str) -> list[Any]:
    return [call for call in mock.mock_calls if str(call[1]) == url]


@pytest.fixture
def live_cloud(mock_cloud: AiohttpClientMocker) -> AiohttpClientMocker:
    """REST mocks for the live view endpoints."""
    mock_cloud.get(DETAIL_URL, json={"code": 200, "data": {}})
    mock_cloud.post(CLOSE_URL, json={"code": 200, "msg": "success"})
    return mock_cloud


def _fake_ws(device: dict[str, Any]):
    async def fake(_api: Any, on_device: Any) -> None:
        pushed = dict(
            device, properties={**device["properties"], "batteryPercentage": 77}
        )
        on_device(pushed)
        await asyncio.Event().wait()  # stay connected until the time limit

    return fake


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _press(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": _entity_id(hass, "button", "live")},
        blocking=True,
    )


async def test_api_live_endpoints(
    hass: HomeAssistant, live_cloud: AiohttpClientMocker
) -> None:
    """Detail is a GET, closing the realtime mode a POST without body (like the app)."""
    api = MinjetApi(async_get_clientsession(hass), USERNAME, PASSWORD)
    await api.async_query_detail(SERIAL)
    await api.async_close_realtime(SERIAL)
    assert _calls(live_cloud, DETAIL_URL)[0][0] == "GET"
    close = _calls(live_cloud, CLOSE_URL)[0]
    assert close[0] == "POST"
    assert close[2] is None


async def test_live_session_updates_then_ends(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    live_cloud: AiohttpClientMocker,
    device: dict[str, Any],
) -> None:
    """Pushes are applied while live; after the limit the realtime mode is closed."""
    with (
        patch(
            "custom_components.minjet.api.MinjetApi.async_run_websocket",
            _fake_ws(device),
        ),
        patch("custom_components.minjet.coordinator.LIVE_DURATION", SHORT),
    ):
        await _setup(hass, mock_entry)
        live_id = _entity_id(hass, "binary_sensor", "live_active")
        battery_id = _entity_id(hass, "sensor", "battery_level")
        assert hass.states.get(live_id).state == "off"

        await _press(hass)
        await asyncio.sleep(0.05)
        await hass.async_block_till_done()
        assert hass.states.get(live_id).state == "on"
        assert hass.states.get(battery_id).state == "77"
        assert len(_calls(live_cloud, DETAIL_URL)) == 1

        await asyncio.sleep(0.3)
        await hass.async_block_till_done()
        assert hass.states.get(live_id).state == "off"
        assert len(_calls(live_cloud, CLOSE_URL)) == 1


async def test_second_press_does_not_start_another_session(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    live_cloud: AiohttpClientMocker,
    device: dict[str, Any],
) -> None:
    """Pressing again while live changes nothing."""
    with (
        patch(
            "custom_components.minjet.api.MinjetApi.async_run_websocket",
            _fake_ws(device),
        ),
        patch("custom_components.minjet.coordinator.LIVE_DURATION", SHORT),
    ):
        await _setup(hass, mock_entry)
        await _press(hass)
        await _press(hass)
        await asyncio.sleep(0.3)
        await hass.async_block_till_done()
        assert len(_calls(live_cloud, DETAIL_URL)) == 1
        assert len(_calls(live_cloud, CLOSE_URL)) == 1


async def test_unload_during_live_closes_realtime(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    live_cloud: AiohttpClientMocker,
    device: dict[str, Any],
) -> None:
    """Unloading the integration while live still ends the realtime mode."""
    with patch(
        "custom_components.minjet.api.MinjetApi.async_run_websocket", _fake_ws(device)
    ):
        await _setup(hass, mock_entry)
        await _press(hass)
        await asyncio.sleep(0.05)
        assert await hass.config_entries.async_unload(mock_entry.entry_id)
        await asyncio.sleep(0.05)
        await hass.async_block_till_done()
    assert len(_calls(live_cloud, CLOSE_URL)) == 1


async def test_close_failure_still_ends_live(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    device: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If the cloud rejects the close call, the live state is still reset and logged."""
    mock_cloud.get(DETAIL_URL, json={"code": 200, "data": {}})
    mock_cloud.post(CLOSE_URL, json={"code": 500, "msg": "busy"})
    with (
        patch(
            "custom_components.minjet.api.MinjetApi.async_run_websocket",
            _fake_ws(device),
        ),
        patch("custom_components.minjet.coordinator.LIVE_DURATION", SHORT),
    ):
        await _setup(hass, mock_entry)
        await _press(hass)
        await asyncio.sleep(0.3)
        await hass.async_block_till_done()
    assert not mock_entry.runtime_data.live_serials
    assert "Could not end the Minjet realtime mode" in caplog.text


async def test_websocket_stream_parsing(
    device: dict[str, Any], socket_enabled: None
) -> None:
    """Only detail messages with a serial reach the callback."""
    seen: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.WebSocketResponse:
        assert request.query["token"] == "tok"
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.send_str('{"msg": "success"}')
        await ws.send_str("not json")
        await ws.send_json({"msg": "success", "data": {"x": 1}, "type": "detail"})
        await ws.send_json({"msg": "success", "data": device, "type": "detail"})
        await ws.close()
        return ws

    app = web.Application()
    app.router.add_get("/ws/device", handler)
    async with TestServer(app) as server, ClientSession() as session:
        api = MinjetApi(
            session,
            USERNAME,
            PASSWORD,
            ws_url=f"ws://127.0.0.1:{server.port}/ws/device",
        )
        api._token = "tok"
        await api.async_run_websocket(seen.append)
    assert [d["serialNum"] for d in seen] == [SERIAL]
