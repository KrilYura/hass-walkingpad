"""Walking Pad Api."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from enum import Enum, unique
from typing import TypeVar

from bleak import BleakError
from bleak.backends.device import BLEDevice
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from ph4_walkingpad.pad import Controller, WalkingPadCurStatus

from .const import BeltState, ConnectionMode, WalkingPadMode, WalkingPadStatus

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


@unique
class WalkingPadConnectionStatus(Enum):
    """An enumeration of the possible connection states."""

    NOT_CONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2


class WalkingPad:
    """The WalkingPad device."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        address: str,
        ble_device: BLEDevice | None = None,
    ) -> None:
        """Create a WalkingPad object."""

        self._hass = hass
        self._name = name
        self._address = address
        self._ble_device = ble_device
        self._controller = Controller()
        self._controller.log_messages_info = False
        self._callbacks: list[Callable[[WalkingPadStatus], None]] = []
        self._disconnect_callbacks: list[Callable[[], None]] = []
        self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
        self._ignore_disconnect_callback = False
        self._lock = asyncio.Lock()
        # When not persistent, control commands release the BLE link after completing.
        self.connection_mode = ConnectionMode.POLLING
        self._register_controller_callbacks()

    def _register_controller_callbacks(self) -> None:
        self._controller.handler_cur_status = self._on_status_update

    def register_disconnect_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked on unexpected BLE disconnect."""
        self._disconnect_callbacks.append(callback)

    def _notify_disconnect_callbacks(self) -> None:
        for callback in self._disconnect_callbacks:
            callback()

    def _on_ble_disconnected(self, _client) -> None:
        """Handle Bleak reporting that the GATT link dropped."""
        was_connected = (
            self._connection_status == WalkingPadConnectionStatus.CONNECTED
        )
        self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
        if self._ignore_disconnect_callback or not was_connected:
            return
        _LOGGER.info("WalkingPad BLE link disconnected")
        self._notify_disconnect_callbacks()

    def _attach_disconnect_callback(self) -> None:
        """Attach disconnect callback to the active Bleak client if possible."""
        client = self._controller.client
        if client is None:
            return
        if hasattr(client, "set_disconnected_callback"):
            client.set_disconnected_callback(self._on_ble_disconnected)
        else:
            # Bleak historically invoked this attribute when the link dropped.
            # Prefer set_disconnected_callback when present; keep as last resort.
            client._disconnected_callback = self._on_ble_disconnected  # noqa: SLF001

    async def _end_cmd(self) -> None:
        await asyncio.sleep(0.75)

    async def _maybe_release(self) -> None:
        """Disconnect after a command when not in persistent mode."""
        if self.connection_mode != ConnectionMode.PERSISTENT:
            await self.disconnect()

    def set_ble_device(self, ble_device: BLEDevice) -> None:
        """Update the cached BLE device from a scanner callback."""
        self._ble_device = ble_device

    def is_currently_visible(self) -> bool:
        """Return True if scanners currently see the WalkingPad advertising."""
        return bluetooth.async_address_present(
            self._hass, self._address, connectable=True
        )

    def _resolve_ble_device(self) -> BLEDevice | None:
        """Refresh the BLE device from Home Assistant's Bluetooth cache."""
        # Prefer an actively seen device; stale cache entries can linger for minutes
        # after the pad is powered off and cause long failed connect attempts.
        if not self.is_currently_visible():
            return None
        ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._address, connectable=True
        )
        if ble_device is not None:
            self._ble_device = ble_device
        return self._ble_device

    def _on_status_update(self, sender, data: WalkingPadCurStatus) -> None:
        """Update current state."""
        try:
            mode = WalkingPadMode(data.manual_mode)
        except ValueError:
            mode = WalkingPadMode.MANUAL

        try:
            belt_state = BeltState(data.belt_state)
        except ValueError:
            belt_state = BeltState.UNKNOWN

        status: WalkingPadStatus = {
            "belt_state": belt_state,
            "speed": data.speed / 10,
            "mode": mode,
            "session_distance": data.dist * 10,
            "session_running_time": data.time,
            "session_steps": data.steps,
            "status_timestamp": data.rtime,
        }

        for callback in self._callbacks:
            callback(status)

    def register_status_callback(
        self, callback: Callable[[WalkingPadStatus], None]
    ) -> None:
        """Register a status callback."""
        self._callbacks.append(callback)

    @property
    def mac(self) -> str:
        """Mac address."""
        return self._address

    @property
    def name(self) -> str:
        """Name."""
        return self._name

    @property
    def connection_status(self) -> WalkingPadConnectionStatus:
        """Connection status."""
        return self._connection_status

    @property
    def connected(self) -> bool:
        """Boolean property to check if the device is connected."""
        return self._connection_status == WalkingPadConnectionStatus.CONNECTED

    async def connect(self) -> None:
        """Connect the device (idempotent when already connected)."""
        async with self._lock:
            await self._connect_locked()

    async def _connect_locked(self) -> None:
        """Connect while holding the session lock."""
        if self._connection_status == WalkingPadConnectionStatus.CONNECTED:
            return
        if self._connection_status == WalkingPadConnectionStatus.CONNECTING:
            _LOGGER.info("Already connecting to WalkingPad")
            return

        _LOGGER.info("Connecting to WalkingPad")
        self._connection_status = WalkingPadConnectionStatus.CONNECTING
        try:
            ble_device = self._resolve_ble_device()
            if ble_device is None:
                _LOGGER.debug(
                    "WalkingPad %s is not currently visible via Bluetooth",
                    self._address,
                )
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
                return
            await self._controller.run(ble_device)
            self._attach_disconnect_callback()
            self._connection_status = WalkingPadConnectionStatus.CONNECTED
            await self._end_cmd()
        except asyncio.CancelledError:
            self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
            raise
        except (BleakError, TimeoutError) as err:
            _LOGGER.warning("Unable to connect to WalkingPad : %s", err)
            self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
        except Exception:  # pylint: disable=broad-except
            _LOGGER.warning("Unable to connect to WalkingPad", exc_info=True)
            self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED

    async def disconnect(self) -> None:
        """Disconnect the device."""
        async with self._lock:
            await self._disconnect_locked()

    async def _disconnect_locked(self) -> None:
        """Disconnect while holding the session lock."""
        if self._connection_status == WalkingPadConnectionStatus.NOT_CONNECTED:
            return
        self._ignore_disconnect_callback = True
        try:
            await asyncio.wait_for(self._controller.disconnect(), timeout=3)
        except (BleakError, TimeoutError, Exception):  # pylint: disable=broad-except
            _LOGGER.debug("Disconnect finished with error", exc_info=True)
        finally:
            self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
            self._ignore_disconnect_callback = False

    async def _ensure_connected_locked(self) -> None:
        """Ensure a live connection while holding the lock."""
        if self._connection_status != WalkingPadConnectionStatus.CONNECTED:
            await self._connect_locked()
        if not self.connected:
            raise HomeAssistantError("Unable to connect to WalkingPad")

    async def _run_command(
        self, operation: Callable[[], Awaitable[T]], *, release: bool = True
    ) -> T:
        """Ensure connection, run a controller operation, optionally release."""
        async with self._lock:
            await self._ensure_connected_locked()
            try:
                result = await operation()
            except BleakError as err:
                _LOGGER.warning("Bluetooth error : %s", err)
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
                self._ignore_disconnect_callback = True
                try:
                    await asyncio.wait_for(self._controller.disconnect(), timeout=3)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.debug(
                        "Disconnect after command error failed", exc_info=True
                    )
                finally:
                    self._ignore_disconnect_callback = False
                self._notify_disconnect_callbacks()
                raise HomeAssistantError(f"Bluetooth error: {err}") from err
        if release:
            await self._maybe_release()
        return result

    async def update_state(self) -> None:
        """Update device state (does not auto-release; coordinator owns that)."""
        await self._run_command(self._controller.ask_stats, release=False)

    async def start_belt(self) -> None:
        """Start the belt."""
        await self._run_command(self._controller.start_belt)

    async def stop_belt(self) -> None:
        """Stop the belt."""
        await self._run_command(self._controller.stop_belt)

    async def set_speed(self, speed: float) -> None:
        """Set the belt speed in km/h."""

        async def _change() -> None:
            speed_tenths = round(speed * 10)
            await self._controller.change_speed(speed_tenths)

        await self._run_command(_change)

    async def switch_mode(self, mode: WalkingPadMode) -> None:
        """Switch the WalkingPad mode."""

        async def _switch() -> None:
            await self._controller.switch_mode(mode.value)

        await self._run_command(_switch)
