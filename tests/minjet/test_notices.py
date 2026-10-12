"""Tests for warning messages: API parsing, timestamp sensor and event entity."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.minjet.api import MinjetApi, parse_server_time
from custom_components.minjet.const import DOMAIN

from .conftest import (
    PASSWORD,
    SERIAL,
    USERNAME,
    notice_response,
    register_cloud,
)


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


def test_server_time_is_utc_plus_8() -> None:
    """The cloud's naive times are China time; they become aware UTC."""
    assert parse_server_time("2026-10-10 13:16:54") == datetime(
        2026, 10, 10, 5, 16, 54, tzinfo=UTC
    )
    assert parse_server_time(None) is None
    assert parse_server_time("garbage") is None


async def test_api_get_notices(
    hass: HomeAssistant, mock_cloud: AiohttpClientMocker
) -> None:
    """The last message per device is returned keyed by serial."""
    api = MinjetApi(async_get_clientsession(hass), USERNAME, PASSWORD)
    notices = await api.async_get_notices()
    assert notices[SERIAL] == {
        "message": "Niedrige SOC",
        "title": "Warning message",
        "time": datetime(2026, 10, 10, 5, 16, 54, tzinfo=UTC),
    }


async def test_last_warning_sensor_and_silent_start(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
) -> None:
    """The sensor shows the UTC time; the existing message fires no event."""
    await _setup(hass, mock_entry)
    sensor = hass.states.get(_entity_id(hass, "sensor", "last_warning"))
    assert sensor.state == "2026-10-10T05:16:54+00:00"
    assert sensor.attributes["message"] == "Niedrige SOC"
    assert sensor.attributes["title"] == "Warning message"
    assert hass.states.get(_entity_id(hass, "event", "warning")).state == "unknown"


async def test_new_warning_fires_event(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    device: dict[str, Any],
) -> None:
    """A newer message triggers the event once; an unchanged one does not."""
    await _setup(hass, mock_entry)
    event_id = _entity_id(hass, "event", "warning")

    register_cloud(mock_cloud, device, notice_response("2026-10-11 13:16:55"))
    mock_entry.runtime_data._notices_fetched = None  # next poll reads notices
    await mock_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(event_id)
    assert state.attributes["event_type"] == "warning"
    assert state.attributes["message"] == "Niedrige SOC"
    assert state.attributes["time"] == "2026-10-11T05:16:55+00:00"
    first_state = state.state

    mock_entry.runtime_data._notices_fetched = None
    await mock_entry.runtime_data.async_refresh()  # same message again
    await hass.async_block_till_done()
    assert hass.states.get(event_id).state == first_state


async def test_notice_failure_does_not_break_updates(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
    device: dict[str, Any],
) -> None:
    """A failing notice endpoint keeps the last warning and the device data."""
    await _setup(hass, mock_entry)
    register_cloud(mock_cloud, device, notices_status=500)
    mock_entry.runtime_data._notices_fetched = None
    await mock_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert mock_entry.runtime_data.last_update_success
    sensor = hass.states.get(_entity_id(hass, "sensor", "last_warning"))
    assert sensor.state == "2026-10-10T05:16:54+00:00"


async def test_notices_polled_every_ten_minutes(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_cloud: AiohttpClientMocker,
) -> None:
    """The device list is polled every update, the notices only every 10 min."""
    await _setup(hass, mock_entry)
    coordinator = mock_entry.runtime_data

    def notice_calls() -> int:
        return sum(
            1 for call in mock_cloud.mock_calls if "queryAppNoticeList" in str(call[1])
        )

    assert notice_calls() == 1
    await coordinator.async_refresh()
    assert notice_calls() == 1  # within 10 minutes: not asked again

    coordinator._notices_fetched -= 601  # pretend 10 minutes have passed
    await coordinator.async_refresh()
    assert notice_calls() == 2
