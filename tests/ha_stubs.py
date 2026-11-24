"""Minimal Home Assistant stubs for unit tests without a full HA install."""

from __future__ import annotations

import sys
import types
from enum import Enum
from typing import Any, Generic, TypeVar
from unittest.mock import MagicMock


class HomeAssistantError(Exception):
    """Stub HA error."""


class ServiceValidationError(HomeAssistantError):
    """Stub validation error."""


def install_ha_stubs() -> None:
    """Install stub modules into sys.modules if homeassistant is missing."""
    try:
        import homeassistant  # noqa: F401
    except ImportError:
        pass
    else:
        return

    ha = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    exceptions = types.ModuleType("homeassistant.exceptions")
    exceptions.HomeAssistantError = HomeAssistantError
    exceptions.ConfigEntryNotReady = HomeAssistantError
    exceptions.ServiceValidationError = ServiceValidationError
    sys.modules["homeassistant.exceptions"] = exceptions

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = MagicMock
    core.callback = lambda f: f
    core.CALLBACK_TYPE = Any
    core.HassJob = MagicMock
    sys.modules["homeassistant.core"] = core

    const_mod = types.ModuleType("homeassistant.const")

    class Platform(str, Enum):
        BINARY_SENSOR = "binary_sensor"
        SENSOR = "sensor"
        SWITCH = "switch"
        NUMBER = "number"
        SELECT = "select"

    const_mod.Platform = Platform
    const_mod.UnitOfLength = types.SimpleNamespace(KILOMETERS="km")
    const_mod.UnitOfSpeed = types.SimpleNamespace(KILOMETERS_PER_HOUR="km/h")
    const_mod.UnitOfTime = types.SimpleNamespace(
        SECONDS="s", MINUTES="min", HOURS="h", DAYS="d"
    )
    const_mod.STATE_ON = "on"
    sys.modules["homeassistant.const"] = const_mod

    class ConfigEntry:
        """Subscriptable config entry stub."""

        def __class_getitem__(cls, item):  # noqa: ANN001
            return cls

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = ConfigEntry
    config_entries.ConfigFlow = object
    config_entries.OptionsFlow = object
    config_entries.CONN_CLASS_LOCAL_POLL = "local_poll"
    sys.modules["homeassistant.config_entries"] = config_entries

    helpers = types.ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers"] = helpers

    update_coordinator = types.ModuleType(
        "homeassistant.helpers.update_coordinator"
    )
    T = TypeVar("T")

    class DataUpdateCoordinator(Generic[T]):
        def __init__(self, *args, **kwargs) -> None:
            self.hass = kwargs.get("hass") or (args[0] if args else None)
            self.data = None
            self.update_interval = kwargs.get("update_interval")
            self._listeners = {}

        async def async_shutdown(self) -> None:
            return None

        async def async_request_refresh(self) -> None:
            return None

        def async_set_updated_data(self, data: T) -> None:
            self.data = data

        def async_update_listeners(self) -> None:
            return None

        def async_add_listener(self, update_callback, context=None):
            return lambda: None

    class CoordinatorEntity(Generic[T]):
        def __init__(self, coordinator: DataUpdateCoordinator[T]) -> None:
            self.coordinator = coordinator

    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.CoordinatorEntity = CoordinatorEntity
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator

    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    device_registry.DeviceInfo = dict
    device_registry.CONNECTION_BLUETOOTH = "bluetooth"
    sys.modules["homeassistant.helpers.device_registry"] = device_registry

    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    entity_registry.async_get = MagicMock()
    sys.modules["homeassistant.helpers.entity_registry"] = entity_registry

    helpers.device_registry = device_registry
    helpers.entity_registry = entity_registry
    helpers.update_coordinator = update_coordinator

    event = types.ModuleType("homeassistant.helpers.event")
    event.async_call_later = MagicMock()
    sys.modules["homeassistant.helpers.event"] = event

    restore_state = types.ModuleType("homeassistant.helpers.restore_state")
    restore_state.RestoreEntity = object
    restore_state.async_get = MagicMock()
    sys.modules["homeassistant.helpers.restore_state"] = restore_state

    typing_mod = types.ModuleType("homeassistant.helpers.typing")
    typing_mod.StateType = Any
    typing_mod.ConfigFlowResult = dict
    sys.modules["homeassistant.helpers.typing"] = typing_mod

    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform.AddEntitiesCallback = Any
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

    components = types.ModuleType("homeassistant.components")
    sys.modules["homeassistant.components"] = components

    bluetooth = types.ModuleType("homeassistant.components.bluetooth")
    bluetooth.async_address_present = MagicMock(return_value=True)
    bluetooth.async_ble_device_from_address = MagicMock(return_value=MagicMock())
    bluetooth.async_scanner_count = MagicMock(return_value=1)
    bluetooth.async_register_callback = MagicMock(return_value=lambda: None)
    bluetooth.BluetoothCallbackMatcher = dict
    bluetooth.BluetoothChange = MagicMock()
    bluetooth.BluetoothScanningMode = types.SimpleNamespace(ACTIVE="active")
    bluetooth.BluetoothServiceInfoBleak = MagicMock
    sys.modules["homeassistant.components.bluetooth"] = bluetooth
    components.bluetooth = bluetooth

    # Platform stubs used only if those modules are imported.
    for name in ("binary_sensor", "sensor", "switch", "number", "select"):
        mod = types.ModuleType(f"homeassistant.components.{name}")
        if name == "binary_sensor":
            class BinarySensorDeviceClass(str, Enum):
                CONNECTIVITY = "connectivity"

            class BinarySensorEntity:
                """Stub binary sensor entity."""

            mod.BinarySensorDeviceClass = BinarySensorDeviceClass
            mod.BinarySensorEntity = BinarySensorEntity
        sys.modules[f"homeassistant.components.{name}"] = mod
        setattr(components, name, mod)

    data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    data_entry_flow.FlowResult = dict
    data_entry_flow.section = MagicMock()
    sys.modules["homeassistant.data_entry_flow"] = data_entry_flow

    ha.exceptions = exceptions
    ha.core = core
    ha.const = const_mod
    ha.config_entries = config_entries
    ha.helpers = helpers
    ha.components = components
