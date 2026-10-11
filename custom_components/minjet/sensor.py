"""Sensors for Minjet."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MinjetConfigEntry
from .entity import MinjetEntity

BATTERY_STATES = {0: "idle", 1: "charging", 2: "discharging"}


@dataclass(frozen=True, kw_only=True)
class MinjetSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor over the ``properties`` dict."""

    value_fn: Callable[[dict[str, Any]], Any]


def _prop(key: str) -> Callable[[dict[str, Any]], Any]:
    return lambda props: props.get(key)


def _battery_power(props: dict[str, Any]) -> float | None:
    """Signed battery power: positive while charging, negative while discharging.

    The cloud reports the magnitude in ``batteryPower`` and the direction in
    ``batteryStatus`` (1 = charging, 2 = discharging, derived from the power
    balance: output = PV - charging + discharging).
    """
    power = props.get("batteryPower")
    sign = {0: 0, 1: 1, 2: -1}.get(props.get("batteryStatus"))
    if power is None or sign is None:
        return None
    return abs(power) * sign


def _millivolt(key: str) -> Callable[[dict[str, Any]], float | None]:
    def value(props: dict[str, Any]) -> float | None:
        raw = props.get(key)
        return None if raw is None else raw / 1000

    return value


def _mapped(key: str, mapping: dict[int, str]) -> Callable[[dict[str, Any]], Any]:
    def value(props: dict[str, Any]) -> str | None:
        raw = props.get(key)
        return None if raw is None else mapping.get(int(raw))

    return value


SENSORS: tuple[MinjetSensorDescription, ...] = (
    MinjetSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_prop("batteryPercentage"),
    ),
    MinjetSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_battery_power,
    ),
    MinjetSensorDescription(
        key="battery_state",
        translation_key="battery_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(BATTERY_STATES.values()),
        value_fn=_mapped("batteryStatus", BATTERY_STATES),
    ),
    MinjetSensorDescription(
        key="pv_power",
        translation_key="pv_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_prop("photovoltaicPower"),
    ),
    MinjetSensorDescription(
        key="output_power",
        translation_key="output_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_prop("outputPower"),
    ),
    MinjetSensorDescription(
        key="smart_meter_power",
        translation_key="smart_meter_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_prop("emFeedbackValue"),
    ),
    MinjetSensorDescription(
        key="energy_generated",
        translation_key="energy_generated",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_prop("photovoltaicTotalGenerate"),
    ),
    MinjetSensorDescription(
        key="energy_used",
        translation_key="energy_used",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_prop("energyTotalUsed"),
    ),
    MinjetSensorDescription(
        key="temperature_1",
        translation_key="temperature_1",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_prop("temperature1"),
    ),
    MinjetSensorDescription(
        key="temperature_2",
        translation_key="temperature_2",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_prop("temperature2"),
    ),
    MinjetSensorDescription(
        key="cell_voltage_min",
        translation_key="cell_voltage_min",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_millivolt("cellVoltMin"),
    ),
    MinjetSensorDescription(
        key="cell_voltage_max",
        translation_key="cell_voltage_max",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_millivolt("cellVoltMax"),
    ),
    MinjetSensorDescription(
        key="discharge_limit",
        translation_key="discharge_limit",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_prop("batteryDischargeLimit"),
    ),
    MinjetSensorDescription(
        key="rated_power",
        translation_key="rated_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_prop("ratedPower"),
    ),
    MinjetSensorDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_prop("WiFiRSSI"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MinjetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        MinjetSensor(coordinator, serial, description)
        for serial in coordinator.data
        for description in SENSORS
    )
    async_add_entities(
        MinjetLastWarningSensor(coordinator, serial) for serial in coordinator.data
    )


class MinjetSensor(MinjetEntity, SensorEntity):
    """A sensor reading one value of a Minjet device."""

    entity_description: MinjetSensorDescription

    def __init__(self, coordinator, serial: str, description) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial)
        self.entity_description = description
        self._attr_unique_id = f"{serial}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self.entity_description.value_fn(self.properties)


class MinjetLastWarningSensor(MinjetEntity, SensorEntity):
    """Time of the latest warning message; text and title are attributes."""

    _attr_translation_key = "last_warning"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, serial: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_last_warning"

    @property
    def _notice(self) -> dict[str, Any]:
        return self.device.get("notice") or {}

    @property
    def native_value(self) -> datetime | None:
        """Return when the latest warning was issued."""
        return self._notice.get("time")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the message text and title."""
        return {
            "message": self._notice.get("message"),
            "title": self._notice.get("title"),
        }
