"""WalkingPad select entities."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WalkingPadConfigEntry
from .const import CONNECTION_MODE_OPTIONS, ConnectionMode
from .coordinator import WalkingPadCoordinator
from .entity import WalkingPadEntity

CONNECTION_MODE_KEY = "walkingpad_connection_mode"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WalkingPadConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WalkingPad select entities."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([WalkingPadConnectionModeSelect(coordinator)])


class WalkingPadConnectionModeSelect(WalkingPadEntity, SelectEntity):
    """Select the BLE connection mode for the WalkingPad."""

    _attr_translation_key = CONNECTION_MODE_KEY
    _attr_icon = "mdi:bluetooth-connect"
    _attr_options = CONNECTION_MODE_OPTIONS

    def __init__(self, coordinator: WalkingPadCoordinator) -> None:
        """Initialize the connection mode select."""
        super().__init__(coordinator, CONNECTION_MODE_KEY)

    @property
    def current_option(self) -> str:
        """Return the current connection mode."""
        return self.coordinator.connection_mode.value

    async def async_select_option(self, option: str) -> None:
        """Set the connection mode."""
        await self.coordinator.async_set_connection_mode(ConnectionMode(option))
        self.async_write_ha_state()
