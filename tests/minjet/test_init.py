"""Tests for setup, entities, push updates and diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.minjet.const import BASE_URL, DOMAIN
from custom_components.minjet.diagnostics import async_get_config_entry_diagnostics

from .conftest import SERIAL, register_cloud


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


async def test_offline_device(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    device: dict[str, Any],
) -> None:
    """deviceStatus != 1 turns the online sensor off."""
    await _setup(hass, mock_entry)
    device["deviceStatus"] = "0"
    register_cloud(mock_cloud, device)
    await mock_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, "binary_sensor", "online").state == "off"


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
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
) -> None:
    """Credentials and identifiers never appear in diagnostics."""
    await _setup(hass, mock_entry)
    result = await async_get_config_entry_diagnostics(hass, mock_entry)
    dump = str(result)
    for secret in ("secret", "user@example.com", SERIAL, "192.0.2.42", "4711"):
        assert secret not in dump
    assert result["devices"][0]["properties"]["batteryPercentage"] == 49.0


async def test_polling_only_no_websocket(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
) -> None:
    """Only REST calls are made: no WebSocket keeps the device in realtime mode."""
    await _setup(hass, mock_entry)
    urls = {str(call[1]) for call in mock_cloud.mock_calls}
    assert all(
        url.startswith("https://app.minjet-energy.com/prod-api/") for url in urls
    )
    assert not any("/ws/" in url for url in urls)


async def test_power_flow_sensors(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    device: dict[str, Any],
) -> None:
    """Charge/discharge split and solar-direct follow output = PV - charge + discharge."""
    await _setup(hass, mock_entry)  # sample: discharging 108 W, PV 44.5 W
    assert float(_state(hass, "sensor", "battery_discharge_power").state) == 108.0
    assert float(_state(hass, "sensor", "battery_charge_power").state) == 0.0
    assert float(_state(hass, "sensor", "pv_direct_power").state) == 44.5

    # charging: PV 137.5 W, 38.7 W into the battery, 98.8 W to the inverter
    device["properties"].update(
        batteryStatus=1, batteryPower=38.7, photovoltaicPower=137.5, outputPower=98.8
    )
    register_cloud(mock_cloud, device)
    await mock_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert float(_state(hass, "sensor", "battery_charge_power").state) == 38.7
    assert float(_state(hass, "sensor", "battery_discharge_power").state) == 0.0
    assert float(_state(hass, "sensor", "pv_direct_power").state) == 98.8
