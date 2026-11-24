"""The walkingpad integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TypeAlias

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import async_get as async_get_restore_state

from .const import (
    CONF_CONNECTION_MODE,
    CONF_MAC,
    CONF_NAME,
    CONF_PREFERRED_MODE,
    CONF_REMOTE_CONTROL_ENABLED,
    CONF_STATUS_UPDATE_INTERVAL,
    DEFAULT_CONNECTION_MODE,
    DEFAULT_STATUS_UPDATE_SECONDS,
    DOMAIN,
    LEGACY_AUTO_STATUS_UPDATES_KEY,
    LEGACY_CONNECTED_KEY,
    ConnectionMode,
    migrate_connection_mode_from_legacy,
    parse_connection_mode,
)
from .coordinator import WalkingPadCoordinator
from .walkingpad import WalkingPad

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
]

_LOGGER = logging.getLogger(__name__)


@dataclass
class WalkingPadRuntimeData:
    """Runtime data for a WalkingPad config entry."""

    device: WalkingPad
    coordinator: WalkingPadCoordinator
    remote_control_signature: tuple[object, object]


WalkingPadConfigEntry: TypeAlias = ConfigEntry[WalkingPadRuntimeData]


def _legacy_bool_from_restore(hass: HomeAssistant, entity_id: str | None) -> bool | None:
    """Read a legacy switch last-state, ignoring unavailable/unknown."""
    if not entity_id:
        return None
    restore_data = async_get_restore_state(hass)
    last = restore_data.last_states.get(entity_id)
    if last is None or last.state.state in (None, "unknown", "unavailable"):
        return None
    return last.state.state == "on"


async def async_migrate_connection_options(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Ensure connection mode and interval exist in entry options."""
    options = dict(entry.options)
    changed = False

    if CONF_CONNECTION_MODE not in options:
        entity_registry = er.async_get(hass)
        mac = entry.data.get(CONF_MAC, "")
        connected_id = entity_registry.async_get_entity_id(
            "switch", DOMAIN, f"{mac}-{LEGACY_CONNECTED_KEY}"
        )
        auto_id = entity_registry.async_get_entity_id(
            "switch", DOMAIN, f"{mac}-{LEGACY_AUTO_STATUS_UPDATES_KEY}"
        )
        stay = _legacy_bool_from_restore(hass, connected_id)
        auto = _legacy_bool_from_restore(hass, auto_id)
        if stay is None and auto is None:
            mode = DEFAULT_CONNECTION_MODE
        else:
            mode = migrate_connection_mode_from_legacy(stay, auto)
        options[CONF_CONNECTION_MODE] = mode.value
        changed = True
        _LOGGER.info(
            "Migrated WalkingPad connection mode to %s for %s",
            mode.value,
            mac,
        )

    if CONF_STATUS_UPDATE_INTERVAL not in options:
        options[CONF_STATUS_UPDATE_INTERVAL] = DEFAULT_STATUS_UPDATE_SECONDS
        changed = True

    if changed:
        hass.config_entries.async_update_entry(entry, options=options)


def async_remove_legacy_connection_switches(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove Connected / Auto status updates switch entities."""
    entity_registry = er.async_get(hass)
    mac = entry.data.get(CONF_MAC, "")
    for key in (LEGACY_CONNECTED_KEY, LEGACY_AUTO_STATUS_UPDATES_KEY):
        entity_id = entity_registry.async_get_entity_id(
            "switch", DOMAIN, f"{mac}-{key}"
        )
        if entity_id:
            entity_registry.async_remove(entity_id)


async def async_update_options(
    hass: HomeAssistant, entry: WalkingPadConfigEntry
) -> None:
    """Reload when remote-control options change; ignore live mode/interval writes."""
    runtime = entry.runtime_data
    new_signature = (
        entry.options.get(CONF_REMOTE_CONTROL_ENABLED),
        entry.options.get(CONF_PREFERRED_MODE),
    )
    if new_signature == runtime.remote_control_signature:
        # Coordinator already applied connection_mode / interval.
        mode = parse_connection_mode(entry.options.get(CONF_CONNECTION_MODE))
        if runtime.coordinator.connection_mode != mode:
            await runtime.coordinator.async_set_connection_mode(mode)
        interval = int(
            entry.options.get(
                CONF_STATUS_UPDATE_INTERVAL, DEFAULT_STATUS_UPDATE_SECONDS
            )
        )
        if runtime.coordinator.status_update_interval_seconds != interval:
            await runtime.coordinator.async_set_status_update_interval(interval)
        return

    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: WalkingPadConfigEntry) -> bool:
    """Set up walkingpad from a config entry."""

    address = entry.data.get(CONF_MAC)

    # Only require a scanner at setup. The pad may be powered off / not advertising.
    if bluetooth.async_scanner_count(hass, connectable=True) < 1:
        raise ConfigEntryNotReady(
            "No bluetooth scanner detected. \
            Enable the bluetooth integration or ensure an esphome device \
            is running as a bluetooth proxy"
        )

    await async_migrate_connection_options(hass, entry)
    async_remove_legacy_connection_switches(hass, entry)

    ble_device = bluetooth.async_ble_device_from_address(
        hass, address, connectable=True
    )
    if ble_device is None:
        _LOGGER.info(
            "WalkingPad %s is not currently visible; setup will continue and connect later",
            address,
        )

    name = entry.data.get(CONF_NAME) or DOMAIN
    walkingpad_device = WalkingPad(hass, name, address, ble_device)
    coordinator = WalkingPadCoordinator(hass, walkingpad_device, entry)

    @callback
    def _async_update_ble(
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Keep the BLE device fresh when advertisements are seen."""
        walkingpad_device.set_ble_device(service_info.device)
        if (
            coordinator.connection_mode == ConnectionMode.PERSISTENT
            and not coordinator.connected
        ):
            hass.async_create_task(coordinator.async_try_reconnect_persistent())

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({"address": address}),
            BluetoothScanningMode.ACTIVE,
        )
    )
    entry.async_on_unload(coordinator.async_shutdown)

    entry.runtime_data = WalkingPadRuntimeData(
        device=walkingpad_device,
        coordinator=coordinator,
        remote_control_signature=(
            entry.options.get(CONF_REMOTE_CONTROL_ENABLED),
            entry.options.get(CONF_PREFERRED_MODE),
        ),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if coordinator.connection_mode == ConnectionMode.PERSISTENT:
        await walkingpad_device.connect()
        if not coordinator.connected:
            await coordinator.async_set_connection_mode(ConnectionMode.POLLING)
        else:
            await coordinator.async_request_refresh()
    elif coordinator.connection_mode == ConnectionMode.POLLING:
        await coordinator.async_request_refresh()

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WalkingPadConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
