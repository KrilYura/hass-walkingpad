"""Walking Pad Api."""

from __future__ import annotations

import asyncio
import logging
from enum import Enum, unique

from bleak import BleakError
from bleak.backends.device import BLEDevice
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from ph4_walkingpad.pad import Controller, WalkingPadCurStatus

from .const import BeltState, WalkingPadMode, WalkingPadStatus

_LOGGER = logging.getLogger(__name__)


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
        self._callbacks = []
        self._disconnect_callbacks = []
        self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
        # When False, control commands release the BLE link after completing.
        self.stay_connected = True
        self._register_controller_callbacks()

    def _register_controller_callbacks(self):
        self._controller.handler_cur_status = self._on_status_update

    def register_disconnect_callback(self, callback) -> None:
        """Register a callback invoked on unexpected BLE disconnect."""
        self._disconnect_callbacks.append(callback)

    def _on_ble_disconnected(self, _client) -> None:
        """Handle Bleak reporting that the GATT link dropped."""
        was_connected = (
            self._connection_status == WalkingPadConnectionStatus.CONNECTED
        )
        self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
        if was_connected:
            _LOGGER.info("WalkingPad BLE link disconnected")
            for callback in self._disconnect_callbacks:
                callback()

    def _attach_disconnect_callback(self) -> None:
        """Attach disconnect callback to the active Bleak client if possible."""
        client = self._controller.client
        if client is None:
            return
        if hasattr(client, "set_disconnected_callback"):
            client.set_disconnected_callback(self._on_ble_disconnected)
        else:
            # Bleak stores this attribute and invokes it when the link drops.
            client._disconnected_callback = self._on_ble_disconnected  # noqa: SLF001

    def _begin_cmd(self) -> asyncio.Lock:
        return asyncio.Lock()

    async def _end_cmd(self):
        await asyncio.sleep(0.75)

    async def _maybe_release(self) -> None:
        """Disconnect after a command when stay-connected mode is off."""
        if not self.stay_connected:
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

        status: WalkingPadStatus = {
            "belt_state": (
                BeltState(data.belt_state)
                if data.belt_state in iter(BeltState)
                else BeltState.UNKNOWN
            ),
            "speed": data.speed / 10,
            "mode": WalkingPadMode(data.manual_mode),
            "session_distance": data.dist * 10,
            "session_running_time": data.time,
            "session_steps": data.steps,
            "status_timestamp": data.rtime,
        }

        if len(self._callbacks) > 0:
            for callback in self._callbacks:
                callback(status)

    def register_status_callback(self, callback) -> None:
        """Register a status callback."""
        self._callbacks.append(callback)

    @property
    def mac(self):
        """Mac address."""
        return self._address

    @property
    def name(self):
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
        """Connect the device."""
        lock = self._begin_cmd()
        if self._connection_status == WalkingPadConnectionStatus.CONNECTING:
            _LOGGER.info("Already connecting to WalkingPad")
            return
        _LOGGER.info("Connecting to WalkingPad")
        async with lock:
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
            except (BleakError, TimeoutError) as err:
                _LOGGER.warning("Unable to connect to WalkingPad : %s", err)
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
            except Exception:  # pylint: disable=broad-except
                _LOGGER.warning("Unable to connect to WalkingPad")
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED

    async def disconnect(self) -> None:
        """Disconnect the device."""
        if self._connection_status == WalkingPadConnectionStatus.NOT_CONNECTED:
            return
        lock = self._begin_cmd()
        async with lock:
            try:
                await asyncio.wait_for(self._controller.disconnect(), timeout=3)
            except (BleakError, TimeoutError, Exception):  # pylint: disable=broad-except
                _LOGGER.debug("Disconnect finished with error", exc_info=True)
            finally:
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED

    async def update_state(self) -> None:
        """Update device state."""
        # Grab the lock so we don't run while another command is running
        if self._connection_status == WalkingPadConnectionStatus.NOT_CONNECTED:
            await self.connect()
        lock = self._begin_cmd()
        async with lock:
            if not self.connected:
                return
            try:
                await self._controller.ask_stats()
                # Skip callback so we don't reset debouncer
            except BleakError as err:
                _LOGGER.warning("Bluetooth error : %s", err)
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED

    async def start_belt(self) -> None:
        """Start the belt."""
        if self._connection_status == WalkingPadConnectionStatus.NOT_CONNECTED:
            await self.connect()
        lock = self._begin_cmd()
        async with lock:
            if not self.connected:
                return
            try:
                await self._controller.start_belt()
            except BleakError as err:
                _LOGGER.warning("Bluetooth error : %s", err)
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
        await self._maybe_release()

    async def stop_belt(self) -> None:
        """Stop the belt."""
        if self._connection_status == WalkingPadConnectionStatus.NOT_CONNECTED:
            await self.connect()
        lock = self._begin_cmd()
        async with lock:
            if not self.connected:
                return
            try:
                await self._controller.stop_belt()
            except BleakError as err:
                _LOGGER.warning("Bluetooth error : %s", err)
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
        await self._maybe_release()

    async def set_speed(self, speed: float) -> None:
        """Set the belt speed in km/h."""
        if self._connection_status == WalkingPadConnectionStatus.NOT_CONNECTED:
            await self.connect()
        lock = self._begin_cmd()
        async with lock:
            if not self.connected:
                return
            try:
                speed_tenths = int(speed * 10)
                await self._controller.change_speed(speed_tenths)
            except BleakError as err:
                _LOGGER.warning("Bluetooth error : %s", err)
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
        await self._maybe_release()

    async def switch_mode(self, mode: WalkingPadMode) -> None:
        """Switch the WalkingPad mode."""
        if self._connection_status == WalkingPadConnectionStatus.NOT_CONNECTED:
            await self.connect()
        lock = self._begin_cmd()
        async with lock:
            if not self.connected:
                return
            try:
                await self._controller.switch_mode(mode.value)
            except BleakError as err:
                _LOGGER.warning("Bluetooth error : %s", err)
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
        await self._maybe_release()
