"""Tests for setup, entities, push updates and diagnostics."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.minjet.api import MinjetAuthError, MinjetConnectionError
from custom_components.minjet.const import BASE_URL, DOMAIN
from custom_components.minjet.diagnostics import async_get_config_entry_diagnostics

from .conftest import SERIAL


def _state(hass: HomeAssistant, platform: str, key: str) -> Any:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{SERIAL}_{key}"
    )
    assert entity_id is not None, key
    return hass.states.get(entity_id)


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_creates_entities(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    no_websocket: None,
) -> None:
    """Values from the device list show up with the right units and signs."""
    await _setup(hass, mock_entry)
    assert mock_entry.state is ConfigEntryState.LOADED

    assert _state(hass, "sensor", "battery_level").state == "49.0"
    # discharging (status 2) -> negative
    assert float(_state(hass, "sensor", "battery_power").state) == -108.0
    assert _state(hass, "sensor", "battery_state").state == "discharging"
    assert _state(hass, "sensor", "pv_power").state == "44.5"
    assert _state(hass, "sensor", "output_power").state == "152.5"
    assert _state(hass, "sensor", "energy_generated").state == "402.1"
    assert _state(hass, "sensor", "energy_used").state == "353.8"
    assert float(_state(hass, "sensor", "cell_voltage_min").state) == 3.282
    assert _state(hass, "select", "priority_mode").state == "discharge_first"
    assert _state(hass, "binary_sensor", "online").state == "on"
    assert _state(hass, "binary_sensor", "smart_meter_connected").state == "on"

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, SERIAL)})
    assert device is not None
    assert device.model == "MH7A-48"
    assert device.name == "Akku"
    assert device.sw_version == "0.03.28"


async def test_push_update_and_throttle(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    no_websocket: None,
    device: dict[str, Any],
) -> None:
    """A pushed device replaces values; bursts inside the throttle are ignored."""
    await _setup(hass, mock_entry)
    coordinator = mock_entry.runtime_data

    device["properties"].update(
        batteryStatus=1, batteryPower=38.7, batteryPercentage=48
    )
    coordinator.async_handle_push(device)
    await hass.async_block_till_done()
    assert float(_state(hass, "sensor", "battery_power").state) == 38.7
    assert _state(hass, "sensor", "battery_state").state == "charging"

    device["properties"]["batteryPercentage"] = 10
    coordinator.async_handle_push(device)  # inside throttle window -> ignored
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "battery_level").state == "48"


async def test_offline_device(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    no_websocket: None,
    device: dict[str, Any],
) -> None:
    """deviceStatus != 1 turns the online sensor off."""
    await _setup(hass, mock_entry)
    device["deviceStatus"] = "0"
    mock_entry.runtime_data.async_handle_push(device)
    await hass.async_block_till_done()
    assert _state(hass, "binary_sensor", "online").state == "off"


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    no_websocket: None,
) -> None:
    """A cloud outage during setup is retried, not failed permanently."""
    aioclient_mock.post(f"{BASE_URL}/login", status=503)
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    no_websocket: None,
) -> None:
    """Wrong credentials put the entry into reauth."""
    aioclient_mock.post(f"{BASE_URL}/login", json={"code": 500, "msg": "bad"})
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(mock_entry.async_get_active_flows(hass, {"reauth"}))


async def test_unload(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    no_websocket: None,
) -> None:
    """Unloading removes the entities' availability."""
    await _setup(hass, mock_entry)
    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.NOT_LOADED


async def test_diagnostics_redacts(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    no_websocket: None,
) -> None:
    """Credentials and identifiers never appear in diagnostics."""
    await _setup(hass, mock_entry)
    result = await async_get_config_entry_diagnostics(hass, mock_entry)
    dump = str(result)
    for secret in ("secret", "user@example.com", SERIAL, "192.0.2.42", "4711"):
        assert secret not in dump
    assert result["devices"][0]["properties"]["batteryPercentage"] == 49.0


async def test_websocket_loop_reconnects_and_applies_push(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    device: dict[str, Any],
) -> None:
    """After a connection error the loop reconnects and pushes reach the entities."""
    calls = 0

    async def fake_ws(_api: Any, on_device: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise MinjetConnectionError("lost")
        device["properties"]["batteryPercentage"] = 77
        on_device(device)
        await asyncio.Event().wait()  # stay connected

    with (
        patch("custom_components.minjet.api.MinjetApi.async_run_websocket", fake_ws),
        patch("custom_components.minjet.coordinator.asyncio.sleep", AsyncMock()),
    ):
        await _setup(hass, mock_entry)
        for _ in range(10):
            await hass.async_block_till_done()
            if calls >= 2:
                break
        await hass.async_block_till_done()
        assert calls >= 2
        assert _state(hass, "sensor", "battery_level").state == "77"
        await hass.config_entries.async_unload(mock_entry.entry_id)


async def test_websocket_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
) -> None:
    """A rejected WebSocket token triggers reauth and ends the loop."""

    async def fake_ws(_api: Any, on_device: Any) -> None:
        raise MinjetAuthError("rejected")

    with patch("custom_components.minjet.api.MinjetApi.async_run_websocket", fake_ws):
        await _setup(hass, mock_entry)
        await hass.async_block_till_done()
    assert any(mock_entry.async_get_active_flows(hass, {"reauth"}))
