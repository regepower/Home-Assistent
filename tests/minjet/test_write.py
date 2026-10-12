"""Tests for the write path: API, select and number entities."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.minjet.api import MinjetApi, MinjetConnectionError
from custom_components.minjet.const import BASE_URL, DOMAIN

from .conftest import PASSWORD, SERIAL, USERNAME, register_cloud

WRITE_URL = f"{BASE_URL}/photovoltaic/setRatedPower/{SERIAL}"


def _writes(aioclient_mock: AiohttpClientMocker) -> list[dict[str, Any]]:
    return [call[2] for call in aioclient_mock.mock_calls if str(call[1]) == WRITE_URL]


def _entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{SERIAL}_{key}"
    )
    assert entity_id is not None
    return entity_id


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_api_set_property(
    hass: HomeAssistant, mock_cloud: AiohttpClientMocker
) -> None:
    """The write goes to the setRatedPower endpoint with key/value JSON."""
    mock_cloud.post(WRITE_URL, json={"code": 200, "msg": "success", "data": 90})
    api = MinjetApi(async_get_clientsession(hass), USERNAME, PASSWORD)
    await api.async_set_property(SERIAL, "batteryChargeLimit", 90)
    assert _writes(mock_cloud) == [{"key": "batteryChargeLimit", "value": 90}]


async def test_api_rejects_unverified_keys(
    hass: HomeAssistant, mock_cloud: AiohttpClientMocker
) -> None:
    """Only whitelisted keys can be written; nothing is sent otherwise."""
    api = MinjetApi(async_get_clientsession(hass), USERNAME, PASSWORD)
    for key in ("ratedPower", "emCommStatus", "batteryDischargeLimit", "evil"):
        with pytest.raises(ValueError, match="not a writable"):
            await api.async_set_property(SERIAL, key, 1)
    assert _writes(mock_cloud) == []


async def test_api_write_rejected_by_cloud(
    hass: HomeAssistant, mock_cloud: AiohttpClientMocker
) -> None:
    """A non-200 body code becomes a connection error."""
    mock_cloud.post(WRITE_URL, json={"code": 500, "msg": "The device is not bound"})
    api = MinjetApi(async_get_clientsession(hass), USERNAME, PASSWORD)
    with pytest.raises(MinjetConnectionError, match="not bound"):
        await api.async_set_property(SERIAL, "batteryChargeLimit", 90)


async def test_select_priority_mode(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
) -> None:
    """Selecting a mode writes 0/1 and updates the state optimistically."""
    mock_cloud.post(WRITE_URL, json={"code": 200, "msg": "success", "data": 1})
    await _setup(hass, mock_entry)
    entity_id = _entity_id(hass, "select", "priority_mode")
    assert hass.states.get(entity_id).state == "discharge_first"

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "storage_first"},
        blocking=True,
    )
    assert _writes(mock_cloud) == [{"key": "batteryPriorityModeStatus", "value": 1}]
    assert hass.states.get(entity_id).state == "storage_first"


async def test_select_write_failure(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
) -> None:
    """A rejected write raises and leaves the state untouched."""
    mock_cloud.post(WRITE_URL, json={"code": 500, "msg": "offline"})
    await _setup(hass, mock_entry)
    entity_id = _entity_id(hass, "select", "priority_mode")
    with pytest.raises(HomeAssistantError, match="offline"):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id, "option": "storage_first"},
            blocking=True,
        )
    assert hass.states.get(entity_id).state == "discharge_first"


async def test_charge_limit_unavailable_in_discharge_first(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
) -> None:
    """The app hides the limits in this mode, so the number is unavailable."""
    await _setup(hass, mock_entry)
    entity_id = _entity_id(hass, "number", "charge_limit")
    assert hass.states.get(entity_id).state == "unavailable"


async def test_charge_limit_write_and_validation(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    device: dict[str, Any],
) -> None:
    """In storage-first mode the limit can be set; it must exceed the discharge limit."""
    device["properties"]["batteryPriorityModeStatus"] = 1
    register_cloud(mock_cloud, device)
    mock_cloud.post(WRITE_URL, json={"code": 200, "msg": "success", "data": 99})
    await _setup(hass, mock_entry)
    entity_id = _entity_id(hass, "number", "charge_limit")
    assert float(hass.states.get(entity_id).state) == 100.0

    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id, "value": 99}, blocking=True
    )
    assert _writes(mock_cloud) == [{"key": "batteryChargeLimit", "value": 99}]
    assert float(hass.states.get(entity_id).state) == 99.0

    # discharge limit is 20 -> 20 is not allowed, nothing is sent
    with pytest.raises(ServiceValidationError, match="discharge limit"):
        await hass.services.async_call(
            "number", "set_value", {"entity_id": entity_id, "value": 20}, blocking=True
        )
    assert len(_writes(mock_cloud)) == 1


async def test_switching_mode_makes_charge_limit_unavailable(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    device: dict[str, Any],
) -> None:
    """Writing mode 0 hides the limit again."""
    device["properties"]["batteryPriorityModeStatus"] = 1
    register_cloud(mock_cloud, device)
    mock_cloud.post(WRITE_URL, json={"code": 200, "msg": "success", "data": 0})
    await _setup(hass, mock_entry)
    number_id = _entity_id(hass, "number", "charge_limit")
    assert hass.states.get(number_id).state != "unavailable"

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": _entity_id(hass, "select", "priority_mode"),
            "option": "discharge_first",
        },
        blocking=True,
    )
    assert hass.states.get(number_id).state == "unavailable"
