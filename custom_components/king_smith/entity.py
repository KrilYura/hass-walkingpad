"""Shared entity helpers for the WalkingPad integration."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .walkingpad import WalkingPad


def walkingpad_device_info(device: WalkingPad) -> DeviceInfo:
    """Return DeviceInfo so entities are linked to the WalkingPad device."""
    return DeviceInfo(
        connections={(dr.CONNECTION_BLUETOOTH, device.mac)},
        identifiers={(DOMAIN, device.mac)},
        name=device.name,
        manufacturer="KingSmith",
    )
