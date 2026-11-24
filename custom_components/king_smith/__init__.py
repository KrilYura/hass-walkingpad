"""The walkingpad integration."""

from __future__ import annotations

import logging
from typing import TypedDict

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

from .const import CONF_MAC, CONF_NAME, DOMAIN
from .coordinator import WalkingPadCoordinator
from .walkingpad import WalkingPad

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER]


class WalkingPadIntegrationData(TypedDict):
    """A type to represent the data stored by the integration for each entity."""

    device: WalkingPad
    coordinator: WalkingPadCoordinator


_LOGGER = logging.getLogger(__name__)


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options and reload platforms."""
    await hass.config_entries.async_unload_platforms(
        entry, [Platform.SWITCH, Platform.NUMBER]
    )
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.SWITCH, Platform.NUMBER]
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up walkingpad from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    address = entry.data.get(CONF_MAC)

    # Only require a scanner at setup. The pad may be powered off / not advertising.
    if bluetooth.async_scanner_count(hass, connectable=True) < 1:
        raise ConfigEntryNotReady(
            "No bluetooth scanner detected. \
            Enable the bluetooth integration or ensure an esphome device \
            is running as a bluetooth proxy"
        )

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
    coordinator = WalkingPadCoordinator(hass, walkingpad_device)

    @callback
    def _async_update_ble(
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Keep the BLE device fresh when advertisements are seen."""
        walkingpad_device.set_ble_device(service_info.device)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({"address": address}),
            BluetoothScanningMode.ACTIVE,
        )
    )

    integration_data: WalkingPadIntegrationData = {
        "device": walkingpad_device,
        "coordinator": coordinator,
    }
    hass.data[DOMAIN][entry.entry_id] = integration_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
