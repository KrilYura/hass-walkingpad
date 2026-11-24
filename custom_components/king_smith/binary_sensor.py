"""WalkingPad binary sensor support."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WalkingPadConfigEntry
from .coordinator import WalkingPadCoordinator
from .entity import WalkingPadEntity

CONNECTION_STATUS_KEY = "walkingpad_connection_status"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WalkingPadConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WalkingPad binary sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([WalkingPadConnectionBinarySensor(coordinator)])


class WalkingPadConnectionBinarySensor(WalkingPadEntity, BinarySensorEntity):
    """Report whether Home Assistant currently holds the WalkingPad BLE link."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = CONNECTION_STATUS_KEY
    _attr_icon = "mdi:bluetooth"

    def __init__(self, coordinator: WalkingPadCoordinator) -> None:
        """Initialize the connection status binary sensor."""
        super().__init__(coordinator, CONNECTION_STATUS_KEY)

    @property
    def is_on(self) -> bool:
        """Return True when the BLE link is connected."""
        return self.coordinator.connected

    @property
    def available(self) -> bool:
        """Connection status stays available in every connection mode."""
        return True
