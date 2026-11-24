"""Shared entity helpers for the WalkingPad integration."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BeltState, ConnectionMode
from .coordinator import WalkingPadCoordinator
from .walkingpad import WalkingPad


def walkingpad_device_info(device: WalkingPad) -> DeviceInfo:
    """Return DeviceInfo so entities are linked to the WalkingPad device."""
    return DeviceInfo(
        connections={(dr.CONNECTION_BLUETOOTH, device.mac)},
        identifiers={(DOMAIN, device.mac)},
        name=device.name,
        manufacturer="KingSmith",
    )


def async_remove_entity_by_unique_id(
    hass, domain: str, unique_id: str
) -> None:
    """Remove a stale entity registry entry if it exists."""
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
    if entity_id:
        entity_registry.async_remove(entity_id)


class WalkingPadEntity(CoordinatorEntity[WalkingPadCoordinator]):
    """Base entity for WalkingPad platforms."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: WalkingPadCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.walkingpad_device.mac}-{key}"
        self._attr_device_info = walkingpad_device_info(coordinator.walkingpad_device)

    @property
    def status_available(self) -> bool:
        """Return True when status-based entities should be available."""
        if not self.coordinator.status_reporting_enabled:
            return False
        if self.coordinator.data.get("belt_state") == BeltState.OFF:
            return False
        if self.coordinator.connection_mode == ConnectionMode.PERSISTENT:
            return self.coordinator.connected
        # Polling keeps last known values between successful polls.
        return True
