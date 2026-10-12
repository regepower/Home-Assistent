"""Shared fixtures for the Minjet tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.minjet.const import BASE_URL, DOMAIN

SERIAL = "TEST0000000001"
USERNAME = "user@example.com"
PASSWORD = "secret"

DEVICE: dict[str, Any] = {
    "deviceId": "4711",
    "productCode": "MH7A-48",
    "productTypeCode": "MH7A",
    "deviceName": SERIAL,
    "customName": "Akku",
    "deviceCurrentVersion": "0.03.28",
    "deviceLatestVersion": "0.03.28",
    "deviceStatus": "1",
    "serialNum": SERIAL,
    "macAddress": SERIAL,
    "properties": {
        "batteryPercentage": 49.0,
        "batteryPower": 108.0,
        "batteryStatus": 2,
        "photovoltaicPower": 44.5,
        "outputPower": 152.5,
        "emFeedbackValue": 10.3,
        "photovoltaicTotalGenerate": 402.1,
        "energyTotalUsed": 353.8,
        "temperature1": 28.0,
        "temperature2": 23.0,
        "cellVoltMin": 3282.0,
        "cellVoltMax": 3299.0,
        "batteryChargeLimit": 100.0,
        "batteryDischargeLimit": 20.0,
        "ratedPower": 150.0,
        "batteryPriorityModeStatus": 0,
        "emCommStatus": 1,
        "WiFiRSSI": -69.0,
        "ip0": "192.0.2.42",
    },
}


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow loading custom_components in every test."""


@pytest.fixture
def device() -> dict[str, Any]:
    """Return a fresh copy of the sample device."""
    return deepcopy(DEVICE)


def notice_response(time: str = "2026-10-10 13:16:54") -> dict[str, Any]:
    """Return a queryAppNoticeList response; times are UTC+8 like the real cloud."""
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "systemList": [],
            "deviceUnReadCount": 1,
            "deviceList": [
                {
                    "deviceId": "4711",
                    "serialNum": SERIAL,
                    "customName": "Akku",
                    "unReadMessageCount": 10,
                    "lastMessage": {
                        "text": "Niedrige SOC",
                        "time": time,
                        "title": "Warning message",
                    },
                }
            ],
        },
    }


def register_cloud(
    aioclient_mock: AiohttpClientMocker,
    device: dict[str, Any],
    notices: dict[str, Any] | None = None,
    notices_status: int = 200,
) -> AiohttpClientMocker:
    """(Re-)register the REST mocks; the JSON body is frozen at registration."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"{BASE_URL}/login", json={"code": 200, "msg": "success", "token": "tok"}
    )
    aioclient_mock.get(
        f"{BASE_URL}/device/queryUserDeviceList",
        json={"code": 200, "msg": "success", "data": [device]},
    )
    aioclient_mock.get(
        f"{BASE_URL}/app/notice/queryAppNoticeList",
        json=notices or notice_response(),
        status=notices_status,
    )
    return aioclient_mock


@pytest.fixture
def mock_cloud(
    aioclient_mock: AiohttpClientMocker, device: dict[str, Any]
) -> AiohttpClientMocker:
    """Mock the Minjet REST endpoints."""
    return register_cloud(aioclient_mock, device)


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Return a config entry for the sample account."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=USERNAME,
        title=USERNAME,
        data={"username": USERNAME, "password": PASSWORD},
    )
