"""Walkingpad number support."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSpeed, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WalkingPadIntegrationData
from .const import (
    CONF_MAC,
    CONF_PREFERRED_MODE,
    CONF_REMOTE_CONTROL_ENABLED,
    DEFAULT_PREFERRED_MODE,
    DOMAIN,
    BeltState,
    WalkingPadMode,
)
from .coordinator import DEFAULT_STATUS_UPDATE_SECONDS, WalkingPadCoordinator
from .entity import walkingpad_device_info

NUMBER_KEY = "walkingpad_speed"
INTERVAL_KEY = "walkingpad_update_interval"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the WalkingPad number entities."""

    entry_data: WalkingPadIntegrationData = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]

    entities: list[NumberEntity] = [WalkingPadUpdateIntervalNumberEntity(coordinator)]

    remote_control_enabled = entry.options.get(CONF_REMOTE_CONTROL_ENABLED, False)
    preferred_mode = entry.options.get(CONF_PREFERRED_MODE, DEFAULT_PREFERRED_MODE)
    manual_mode = WalkingPadMode.MANUAL.name.lower()

    if remote_control_enabled and preferred_mode == manual_mode:
        entities.append(WalkingPadSpeedNumberEntity(coordinator))
    else:
        entity_registry = er.async_get(hass)
        mac_address = entry.data.get(CONF_MAC)
        unique_id = f"{mac_address}-{NUMBER_KEY}"
        entity_id = entity_registry.async_get_entity_id("number", DOMAIN, unique_id)
        if entity_id:
            entity_registry.async_remove(entity_id)

    async_add_entities(entities)


class WalkingPadUpdateIntervalNumberEntity(NumberEntity, RestoreEntity):
    """Configure the status polling interval in seconds."""

    _attr_native_min_value = 1
    _attr_native_max_value = 86400
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_has_entity_name = True
    _attr_translation_key = INTERVAL_KEY
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: WalkingPadCoordinator) -> None:
        """Initialize the update interval number."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.walkingpad_device.mac}-{INTERVAL_KEY}"
        self._attr_device_info = walkingpad_device_info(coordinator.walkingpad_device)

    @property
    def native_value(self) -> float:
        """Return the configured interval in seconds."""
        return float(self.coordinator.status_update_interval_seconds)

    async def async_added_to_hass(self) -> None:
        """Restore the previous interval and apply it."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (None, "unknown", "unavailable"):
            try:
                seconds = int(float(last_state.state))
            except (TypeError, ValueError):
                seconds = DEFAULT_STATUS_UPDATE_SECONDS
        else:
            seconds = DEFAULT_STATUS_UPDATE_SECONDS
        await self.coordinator.async_set_status_update_interval(seconds)

    async def async_set_native_value(self, value: float) -> None:
        """Set the status polling interval."""
        await self.coordinator.async_set_status_update_interval(int(value))
        self.async_write_ha_state()


class WalkingPadSpeedNumberEntity(
    CoordinatorEntity[WalkingPadCoordinator], NumberEntity
):
    """Represent the WalkingPad speed number."""

    _attr_native_min_value = 0.5
    _attr_native_max_value = 6.0
    _attr_native_step = 0.1
    _attr_mode = NumberMode.AUTO
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_has_entity_name = True
    _attr_translation_key = "walkingpad_speed"

    def __init__(self, coordinator: WalkingPadCoordinator) -> None:
        """Initialize the speed number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.walkingpad_device.mac}-{NUMBER_KEY}"
        self._attr_device_info = walkingpad_device_info(coordinator.walkingpad_device)

    @property
    def native_value(self) -> float:
        """Return the current speed."""
        return self.coordinator.data.get("speed", 0.0)

    async def async_set_native_value(self, value: float) -> None:
        """Set the speed."""
        belt_state = self.coordinator.data.get("belt_state")
        if belt_state not in [BeltState.ACTIVE, BeltState.STARTING]:
            return
        await self.coordinator.walkingpad_device.set_speed(value)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self.coordinator.stay_connected:
            return self.coordinator.connected
        # Connect-on-demand keeps last known values between polls.
        return True
