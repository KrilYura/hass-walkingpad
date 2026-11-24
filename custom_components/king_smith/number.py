"""Walkingpad number support."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfSpeed, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WalkingPadConfigEntry
from .const import (
    CONF_MAC,
    CONF_PREFERRED_MODE,
    CONF_REMOTE_CONTROL_ENABLED,
    DEFAULT_PREFERRED_MODE,
    BeltState,
    WalkingPadMode,
)
from .coordinator import WalkingPadCoordinator
from .entity import WalkingPadEntity, async_remove_entity_by_unique_id

NUMBER_KEY = "walkingpad_speed"
INTERVAL_KEY = "walkingpad_update_interval"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WalkingPadConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WalkingPad number entities."""
    coordinator = entry.runtime_data.coordinator

    entities: list[NumberEntity] = [WalkingPadUpdateIntervalNumberEntity(coordinator)]

    remote_control_enabled = entry.options.get(CONF_REMOTE_CONTROL_ENABLED, False)
    preferred_mode = entry.options.get(CONF_PREFERRED_MODE, DEFAULT_PREFERRED_MODE)
    manual_mode = WalkingPadMode.MANUAL.name.lower()

    if remote_control_enabled and preferred_mode == manual_mode:
        entities.append(WalkingPadSpeedNumberEntity(coordinator))
    else:
        mac_address = entry.data.get(CONF_MAC)
        async_remove_entity_by_unique_id(
            hass, "number", f"{mac_address}-{NUMBER_KEY}"
        )

    async_add_entities(entities)


class WalkingPadUpdateIntervalNumberEntity(WalkingPadEntity, NumberEntity):
    """Configure the status polling interval in seconds."""

    _attr_native_min_value = 1
    _attr_native_max_value = 86400
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_translation_key = INTERVAL_KEY
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: WalkingPadCoordinator) -> None:
        """Initialize the update interval number."""
        super().__init__(coordinator, INTERVAL_KEY)

    @property
    def native_value(self) -> float:
        """Return the configured interval in seconds."""
        return float(self.coordinator.status_update_interval_seconds)

    async def async_set_native_value(self, value: float) -> None:
        """Set the status polling interval."""
        await self.coordinator.async_set_status_update_interval(int(value))
        self.async_write_ha_state()


class WalkingPadSpeedNumberEntity(WalkingPadEntity, NumberEntity):
    """Represent the WalkingPad speed number."""

    _attr_native_min_value = 0.5
    _attr_native_max_value = 6.0
    _attr_native_step = 0.1
    _attr_mode = NumberMode.AUTO
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_translation_key = "walkingpad_speed"

    def __init__(self, coordinator: WalkingPadCoordinator) -> None:
        """Initialize the speed number."""
        super().__init__(coordinator, NUMBER_KEY)

    @property
    def native_value(self) -> float:
        """Return the current speed."""
        return self.coordinator.data.get("speed", 0.0)

    async def async_set_native_value(self, value: float) -> None:
        """Set the speed."""
        belt_state = self.coordinator.data.get("belt_state")
        if belt_state not in [BeltState.ACTIVE, BeltState.STARTING]:
            raise ServiceValidationError(
                "Speed can only be changed while the belt is active"
            )
        await self.coordinator.walkingpad_device.set_speed(value)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.status_available
