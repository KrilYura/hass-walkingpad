"""Tests for WalkingPadCoordinator connection-mode behaviour."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.king_smith.const import (
    CONF_CONNECTION_MODE,
    CONF_STATUS_UPDATE_INTERVAL,
    ConnectionMode,
)
from custom_components.king_smith.coordinator import WalkingPadCoordinator


def _mock_entry(mode: ConnectionMode = ConnectionMode.POLLING, interval: int = 60):
    entry = MagicMock()
    entry.options = {
        CONF_CONNECTION_MODE: mode.value,
        CONF_STATUS_UPDATE_INTERVAL: interval,
    }
    entry.entry_id = "test"
    return entry


def _mock_device(*, connected: bool = False) -> MagicMock:
    device = MagicMock()
    device.connected = connected
    device.connection_mode = ConnectionMode.POLLING
    device.connect = AsyncMock()
    device.disconnect = AsyncMock()
    device.update_state = AsyncMock()
    device.is_currently_visible = MagicMock(return_value=True)
    device.register_status_callback = MagicMock()
    device.register_disconnect_callback = MagicMock()
    return device


def _build_coordinator(
    hass: MagicMock, device: MagicMock, entry: MagicMock
) -> WalkingPadCoordinator:
    with patch(
        "custom_components.king_smith.coordinator.DataUpdateCoordinator.__init__",
        return_value=None,
    ):
        coordinator = WalkingPadCoordinator.__new__(WalkingPadCoordinator)
        WalkingPadCoordinator.__init__(coordinator, hass, device, entry)
        coordinator.hass = hass
        coordinator.async_update_listeners = MagicMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.async_set_updated_data = MagicMock()
        coordinator._listeners = {}  # noqa: SLF001
        return coordinator


@pytest.fixture
def hass() -> MagicMock:
    """Minimal Home Assistant mock."""
    mock_hass = MagicMock()
    mock_hass.loop = MagicMock()
    mock_hass.config_entries.async_update_entry = MagicMock()
    return mock_hass


@pytest.mark.asyncio
async def test_passive_skips_refresh(hass: MagicMock) -> None:
    """Passive mode does not poll."""
    entry = _mock_entry(ConnectionMode.PASSIVE)
    device = _mock_device()
    coordinator = _build_coordinator(hass, device, entry)

    assert coordinator.connection_mode is ConnectionMode.PASSIVE
    assert coordinator.status_reporting_enabled is False
    result = await coordinator._async_update_data()  # noqa: SLF001
    device.update_state.assert_not_called()
    assert result is coordinator.data


@pytest.mark.asyncio
async def test_polling_disconnects_in_finally(hass: MagicMock) -> None:
    """Polling mode disconnects after a status update."""
    entry = _mock_entry(ConnectionMode.POLLING)
    device = _mock_device(connected=True)
    coordinator = _build_coordinator(hass, device, entry)

    async def update_state() -> None:
        coordinator.data["status_timestamp"] = 100

    device.update_state = AsyncMock(side_effect=update_state)

    with patch(
        "custom_components.king_smith.coordinator.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await coordinator._async_update_data()  # noqa: SLF001

    device.disconnect.assert_awaited()


@pytest.mark.asyncio
async def test_persistent_connect_failure_falls_back_to_polling(
    hass: MagicMock,
) -> None:
    """Selecting persistent without a successful connect falls back to polling."""
    entry = _mock_entry(ConnectionMode.POLLING)
    device = _mock_device(connected=False)
    coordinator = _build_coordinator(hass, device, entry)

    await coordinator.async_set_connection_mode(ConnectionMode.PERSISTENT)

    assert coordinator.connection_mode is ConnectionMode.POLLING
    assert device.connection_mode is ConnectionMode.POLLING
    hass.config_entries.async_update_entry.assert_called()


@pytest.mark.asyncio
async def test_link_loss_falls_back_to_polling(hass: MagicMock) -> None:
    """Unexpected disconnect while persistent falls back to polling."""
    entry = _mock_entry(ConnectionMode.PERSISTENT)
    device = _mock_device(connected=True)
    coordinator = _build_coordinator(hass, device, entry)

    await coordinator._async_handle_unexpected_disconnect()  # noqa: SLF001

    assert coordinator.connection_mode is ConnectionMode.POLLING
    coordinator.async_set_updated_data.assert_called()


@pytest.mark.asyncio
async def test_set_passive_disconnects(hass: MagicMock) -> None:
    """Switching to passive disconnects the device."""
    entry = _mock_entry(ConnectionMode.POLLING)
    device = _mock_device(connected=True)
    coordinator = _build_coordinator(hass, device, entry)

    await coordinator.async_set_connection_mode(ConnectionMode.PASSIVE)

    assert coordinator.connection_mode is ConnectionMode.PASSIVE
    device.disconnect.assert_awaited()
    assert coordinator.status_reporting_enabled is False
