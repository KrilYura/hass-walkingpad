"""Tests for WalkingPad command serialization."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.king_smith.const import ConnectionMode
from custom_components.king_smith.walkingpad import (
    WalkingPad,
    WalkingPadConnectionStatus,
)


@pytest.fixture
def walkingpad() -> WalkingPad:
    """Create a WalkingPad with a mocked controller and visible BLE device."""
    hass = MagicMock()
    with (
        patch(
            "custom_components.king_smith.walkingpad.Controller"
        ) as controller_cls,
        patch(
            "custom_components.king_smith.walkingpad.bluetooth.async_address_present",
            return_value=True,
        ),
        patch(
            "custom_components.king_smith.walkingpad.bluetooth.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
    ):
        controller = controller_cls.return_value
        controller.run = AsyncMock()
        controller.disconnect = AsyncMock()
        controller.ask_stats = AsyncMock()
        controller.start_belt = AsyncMock()
        controller.stop_belt = AsyncMock()
        controller.change_speed = AsyncMock()
        controller.switch_mode = AsyncMock()
        controller.client = MagicMock()
        pad = WalkingPad(hass, "Pad", "aa:bb:cc:dd:ee:ff", MagicMock())
        pad.connection_mode = ConnectionMode.POLLING
        # Skip post-connect settle sleep in tests.
        pad._end_cmd = AsyncMock()  # noqa: SLF001
        return pad


@pytest.mark.asyncio
async def test_connect_is_idempotent(walkingpad: WalkingPad) -> None:
    """A second connect while already connected does not re-run the controller."""
    await walkingpad.connect()
    assert walkingpad.connected
    walkingpad._controller.run.reset_mock()  # noqa: SLF001
    await walkingpad.connect()
    walkingpad._controller.run.assert_not_called()  # noqa: SLF001


@pytest.mark.asyncio
async def test_update_and_stop_are_serialized(walkingpad: WalkingPad) -> None:
    """Overlapping update_state and stop_belt do not interleave controller calls."""
    order: list[str] = []

    async def ask_stats() -> None:
        order.append("ask_start")
        await asyncio.sleep(0.05)
        order.append("ask_end")

    async def stop_belt() -> None:
        order.append("stop_start")
        await asyncio.sleep(0.01)
        order.append("stop_end")

    walkingpad._controller.ask_stats = ask_stats  # noqa: SLF001
    walkingpad._controller.stop_belt = stop_belt  # noqa: SLF001
    walkingpad._connection_status = WalkingPadConnectionStatus.CONNECTED  # noqa: SLF001
    walkingpad.connection_mode = ConnectionMode.PERSISTENT

    await asyncio.gather(walkingpad.update_state(), walkingpad.stop_belt())

    assert order in (
        ["ask_start", "ask_end", "stop_start", "stop_end"],
        ["stop_start", "stop_end", "ask_start", "ask_end"],
    )
    # Must not interleave the two operations.
    assert "ask_start" in order and "ask_end" in order
    ask_start = order.index("ask_start")
    ask_end = order.index("ask_end")
    stop_start = order.index("stop_start")
    stop_end = order.index("stop_end")
    ask_range = range(ask_start, ask_end + 1)
    assert stop_start not in ask_range or stop_start == ask_start
    assert not (ask_start < stop_start < ask_end)
    assert not (stop_start < ask_start < stop_end)


@pytest.mark.asyncio
async def test_command_raises_when_connect_fails(walkingpad: WalkingPad) -> None:
    """Commands surface HomeAssistantError when the pad cannot be connected."""
    with (
        patch.object(walkingpad, "is_currently_visible", return_value=False),
        pytest.raises(HomeAssistantError),
    ):
        await walkingpad.stop_belt()


@pytest.mark.asyncio
async def test_connection_callback_tracks_link(walkingpad: WalkingPad) -> None:
    """Connection callbacks fire when the live BLE connected flag flips."""
    events: list[bool] = []
    walkingpad.register_connection_callback(events.append)

    await walkingpad.connect()
    assert events == [True]
    assert walkingpad.connected

    await walkingpad.disconnect()
    assert events == [True, False]
    assert not walkingpad.connected
