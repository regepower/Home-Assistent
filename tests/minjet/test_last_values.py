"""Tests that the last known values are shown instead of unknown/unavailable."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.minjet.const import BASE_URL, DOMAIN, STALE_AFTER

from .conftest import SERIAL, register_cloud

BATTERY_ENTITY = "sensor.akku_battery"


def _state(hass: HomeAssistant, platform: str, key: str) -> State:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{SERIAL}_{key}"
    )
    assert entity_id is not None
    return hass.states.get(entity_id)


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_missing_values_keep_last_known(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    device: dict[str, Any],
) -> None:
    """A value that is missing or null in a later poll keeps its last value."""
    await _setup(hass, mock_entry)
    del device["properties"]["batteryPercentage"]
    device["properties"]["photovoltaicPower"] = None
    device["properties"]["outputPower"] = 99.0
    register_cloud(mock_cloud, device)
    await mock_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert _state(hass, "sensor", "battery_level").state == "49.0"
    assert _state(hass, "sensor", "pv_power").state == "44.5"
    assert _state(hass, "sensor", "output_power").state == "99.0"  # new value wins


async def test_short_outage_keeps_values_available(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    device: dict[str, Any],
) -> None:
    """One failed poll keeps the values; only a long outage makes them unavailable."""
    await _setup(hass, mock_entry)
    coordinator = mock_entry.runtime_data

    mock_cloud.clear_requests()
    mock_cloud.post(f"{BASE_URL}/login", json={"code": 200, "token": "tok"})
    mock_cloud.get(f"{BASE_URL}/device/queryUserDeviceList", status=503)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert _state(hass, "sensor", "battery_level").state == "49.0"

    coordinator.last_success -= STALE_AFTER.total_seconds() + 1
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "battery_level").state == "unavailable"

    register_cloud(mock_cloud, device)  # cloud back
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, "sensor", "battery_level").state == "49.0"


async def test_restart_restores_value_the_cloud_does_not_send(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    device: dict[str, Any],
) -> None:
    """After a restart a value missing in the first poll comes from the last state."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(BATTERY_ENTITY, "61"),
                {"native_value": 61, "native_unit_of_measurement": "%"},
            )
        ],
    )
    del device["properties"]["batteryPercentage"]
    register_cloud(aioclient_mock, device)
    await _setup(hass, mock_entry)

    state = _state(hass, "sensor", "battery_level")
    assert state.entity_id == BATTERY_ENTITY
    assert state.state == "61"
