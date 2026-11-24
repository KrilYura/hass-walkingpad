"""Walkingpad switch support."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WalkingPadConfigEntry
from .const import (
    CONF_MAC,
    CONF_PREFERRED_MODE,
    CONF_REMOTE_CONTROL_ENABLED,
    DEFAULT_PREFERRED_MODE,
    TEMPORARY_STATE_EXPIRY_SECONDS,
    BeltState,
    WalkingPadMode,
)
from .coordinator import WalkingPadCoordinator
from .entity import WalkingPadEntity, async_remove_entity_by_unique_id
from .utils import TemporaryValue

SWITCH_KEY = "walkingpad_belt_switch"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WalkingPadConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WalkingPad switches."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SwitchEntity] = []

    if entry.options.get(CONF_REMOTE_CONTROL_ENABLED, False):
        preferred_mode = entry.options.get(CONF_PREFERRED_MODE, DEFAULT_PREFERRED_MODE)
        manual_mode = WalkingPadMode.MANUAL.name.lower()
        if preferred_mode == manual_mode:
            entities.append(WalkingPadBeltSwitchManual(coordinator))
        else:
            entities.append(WalkingPadBeltSwitchAuto(coordinator))
    else:
        mac_address = entry.data.get(CONF_MAC)
        async_remove_entity_by_unique_id(
            hass, "switch", f"{mac_address}-{SWITCH_KEY}"
        )

    async_add_entities(entities)


class WalkingPadBeltSwitchBase(WalkingPadEntity, SwitchEntity, ABC):
    """Base class for WalkingPad belt switch entities."""

    entity_description: SwitchEntityDescription
    _temporary_belt_state: TemporaryValue[BeltState]
    _temporary_mode: TemporaryValue[WalkingPadMode]

    @staticmethod
    def _create_entity_description(translation_key: str) -> SwitchEntityDescription:
        """Create an entity description with the given translation key."""
        return SwitchEntityDescription(
            device_class=SwitchDeviceClass.SWITCH,
            icon="mdi:cog-play",
            key=SWITCH_KEY,
            translation_key=translation_key,
            has_entity_name=True,
        )

    def __init__(self, coordinator: WalkingPadCoordinator) -> None:
        """Initialize the belt switch."""
        self._temporary_belt_state = TemporaryValue[BeltState]()
        self._temporary_mode = TemporaryValue[WalkingPadMode]()
        self.entity_description = self._create_entity_description(
            "walkingpad_belt_switch"
        )
        super().__init__(coordinator, self.entity_description.key)

    @property
    def available(self) -> bool:
        """Return if the belt switch is available."""
        return self.status_available

    def _clear_temporary_if_status_newer(self) -> None:
        """Clear optimistic state once a fresh status notification arrives."""
        current_timestamp = self.coordinator.data.get("status_timestamp", 0)
        if (
            self._temporary_belt_state.has_value
            and current_timestamp > self._temporary_belt_state.set_at_status_timestamp
        ):
            self._temporary_belt_state.reset()
        if (
            self._temporary_mode.has_value
            and current_timestamp > self._temporary_mode.set_at_status_timestamp
        ):
            self._temporary_mode.reset()

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        self._clear_temporary_if_status_newer()
        current_timestamp = time.time()
        current_belt_state = self.coordinator.data.get("belt_state")

        if (
            self._temporary_belt_state.has_value
            and current_belt_state != BeltState.STARTING
            and current_timestamp > self._temporary_belt_state.expiration_timestamp
        ):
            self._temporary_belt_state.reset()

        belt_state = self._temporary_belt_state.peek(
            current_belt_state or BeltState.STOPPED
        )
        return belt_state in [BeltState.ACTIVE, BeltState.STARTING]

    def set_temporary_belt_state(self, belt_state: BeltState) -> None:
        """Set a temporary belt state."""
        self._temporary_belt_state.set(
            belt_state,
            time.time() + TEMPORARY_STATE_EXPIRY_SECONDS,
            set_at_status_timestamp=self.coordinator.data.get("status_timestamp", 0),
        )

    def set_temporary_mode(self, mode: WalkingPadMode) -> None:
        """Set a temporary mode."""
        self._temporary_mode.set(
            mode,
            time.time() + TEMPORARY_STATE_EXPIRY_SECONDS,
            set_at_status_timestamp=self.coordinator.data.get("status_timestamp", 0),
        )

    @abstractmethod
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""

    @abstractmethod
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""


class WalkingPadBeltSwitchManual(WalkingPadBeltSwitchBase):
    """Represent the WalkingPad belt switch in manual mode."""

    def __init__(self, coordinator: WalkingPadCoordinator) -> None:
        """Initialize the belt switch."""
        super().__init__(coordinator)
        self.entity_description = self._create_entity_description(
            "walkingpad_belt_switch_manual"
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        current_mode = self.coordinator.data.get("mode")
        try:
            if current_mode != WalkingPadMode.MANUAL:
                await self.coordinator.walkingpad_device.switch_mode(
                    WalkingPadMode.MANUAL
                )
                await asyncio.sleep(1.5)
            self.set_temporary_mode(WalkingPadMode.MANUAL)
            self.set_temporary_belt_state(BeltState.STARTING)
            await self.coordinator.walkingpad_device.start_belt()
        except HomeAssistantError:
            self._temporary_belt_state.reset()
            self._temporary_mode.reset()
            raise
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.set_temporary_belt_state(BeltState.STOPPED)
        try:
            await self.coordinator.walkingpad_device.stop_belt()
        except HomeAssistantError:
            self._temporary_belt_state.reset()
            raise
        self.async_write_ha_state()


class WalkingPadBeltSwitchAuto(WalkingPadBeltSwitchBase):
    """Represent the WalkingPad belt switch in auto mode."""

    def __init__(self, coordinator: WalkingPadCoordinator) -> None:
        """Initialize the belt switch."""
        super().__init__(coordinator)
        self.entity_description = self._create_entity_description(
            "walkingpad_belt_switch_auto"
        )

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        self._clear_temporary_if_status_newer()
        current_timestamp = time.time()
        current_mode = self.coordinator.data.get("mode")
        current_belt_state = self.coordinator.data.get("belt_state")

        mode = self._temporary_mode.get(
            current_timestamp, current_mode or WalkingPadMode.MANUAL
        )
        belt_state = self._temporary_belt_state.get(
            current_timestamp, current_belt_state or BeltState.STOPPED
        )

        if mode == WalkingPadMode.AUTO:
            return True
        if mode == WalkingPadMode.STANDBY:
            return False
        return belt_state in [BeltState.ACTIVE, BeltState.STARTING]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.set_temporary_mode(WalkingPadMode.AUTO)
        try:
            await self.coordinator.walkingpad_device.switch_mode(WalkingPadMode.AUTO)
        except HomeAssistantError:
            self._temporary_mode.reset()
            raise
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.set_temporary_mode(WalkingPadMode.STANDBY)
        self.set_temporary_belt_state(BeltState.STOPPED)
        try:
            await self.coordinator.walkingpad_device.switch_mode(WalkingPadMode.STANDBY)
        except HomeAssistantError:
            self._temporary_mode.reset()
            self._temporary_belt_state.reset()
            raise
        self.async_write_ha_state()
