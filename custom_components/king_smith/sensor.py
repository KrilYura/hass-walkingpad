"""WalkingPad sensor support."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength, UnitOfSpeed, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import WalkingPadConfigEntry
from .const import BeltState, WalkingPadMode, WalkingPadStatus
from .coordinator import WalkingPadCoordinator
from .entity import WalkingPadEntity


@dataclass(kw_only=True)
class WalkingPadSensorEntityDescription(SensorEntityDescription):
    """Describes a WalkingPad sensor entity."""

    value_fn: Callable[[WalkingPadStatus], StateType]
    # When True, entity stays available while status reporting is enabled,
    # including when the pad is unreachable (state reports "off").
    available_when_off: bool = False


SENSORS: tuple[WalkingPadSensorEntityDescription, ...] = (
    WalkingPadSensorEntityDescription(
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:walk",
        key="walkingpad_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        translation_key="walkingpad_distance",
        value_fn=lambda status: status.get("session_distance", 0.0) / 1000,
    ),
    WalkingPadSensorEntityDescription(
        icon="mdi:shoe-print",
        key="walkingpad_steps",
        native_unit_of_measurement="steps",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        translation_key="walkingpad_steps",
        value_fn=lambda status: status.get("session_steps", 0),
    ),
    WalkingPadSensorEntityDescription(
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer",
        key="walkingpad_duration_minutes",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        translation_key="walkingpad_duration_minutes",
        value_fn=lambda status: round(status.get("session_running_time", 0) / 60, 1),
    ),
    WalkingPadSensorEntityDescription(
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer",
        key="walkingpad_duration_hours",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        translation_key="walkingpad_duration_hours",
        value_fn=lambda status: round(status.get("session_running_time", 0) / 3600, 4),
    ),
    WalkingPadSensorEntityDescription(
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer",
        key="walkingpad_duration_days",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        translation_key="walkingpad_duration_days",
        value_fn=lambda status: round(status.get("session_running_time", 0) / 86400, 6),
    ),
    WalkingPadSensorEntityDescription(
        device_class=SensorDeviceClass.SPEED,
        icon="mdi:speedometer",
        key="walkingpad_current_speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="walkingpad_current_speed",
        value_fn=lambda status: status.get("speed", 0.0),
    ),
    WalkingPadSensorEntityDescription(
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:state-machine",
        key="walkingpad_state",
        options=[e.name.lower() for e in BeltState],
        translation_key="walkingpad_state",
        value_fn=lambda status: status.get(
            "belt_state", BeltState.UNKNOWN
        ).name.lower(),
        available_when_off=True,
    ),
    WalkingPadSensorEntityDescription(
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:cog",
        key="walkingpad_mode",
        options=[e.name.lower() for e in WalkingPadMode],
        translation_key="walkingpad_mode",
        value_fn=lambda status: status.get("mode", WalkingPadMode.MANUAL).name.lower(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WalkingPadConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WalkingPad sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        WalkingPadSensor(coordinator, description) for description in SENSORS
    )


class WalkingPadSensor(WalkingPadEntity, SensorEntity):
    """Represent a WalkingPad sensor."""

    entity_description: WalkingPadSensorEntityDescription

    def __init__(
        self,
        coordinator: WalkingPadCoordinator,
        entity_description: WalkingPadSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = entity_description
        super().__init__(coordinator, entity_description.key)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.status_reporting_enabled:
            return False
        if self.entity_description.available_when_off:
            return True
        return self.status_available
