"""The Walking Pad Coordinator."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_CONNECTION_MODE,
    CONF_STATUS_UPDATE_INTERVAL,
    DEFAULT_STATUS_UPDATE_SECONDS,
    DOMAIN,
    BeltState,
    ConnectionMode,
    WalkingPadMode,
    WalkingPadStatus,
    parse_connection_mode,
)
from .walkingpad import WalkingPad

_LOGGER = logging.getLogger(__name__)

# Connect can take up to ~10s; leave room for ask_stats + disconnect.
STATUS_UPDATE_TIMEOUT_SECONDS = 20

# Wait for the status notification after ask_stats before releasing the BLE link.
STATUS_NOTIFICATION_WAIT_SECONDS = 0.75


class WalkingPadCoordinator(DataUpdateCoordinator[WalkingPadStatus]):
    """WalkingPad coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        walkingpad_device: WalkingPad,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialise WalkingPad coordinator."""
        self.config_entry = config_entry
        self.walkingpad_device = walkingpad_device
        self.walkingpad_device.register_status_callback(self._async_handle_update)
        self.walkingpad_device.register_disconnect_callback(
            self._async_on_device_disconnected
        )

        options = config_entry.options
        mode = parse_connection_mode(options.get(CONF_CONNECTION_MODE))
        interval = int(
            options.get(CONF_STATUS_UPDATE_INTERVAL, DEFAULT_STATUS_UPDATE_SECONDS)
        )
        interval = max(1, interval)

        self.connection_mode = mode
        self.status_update_interval_seconds = interval
        self.walkingpad_device.connection_mode = mode

        update_interval = (
            None
            if mode == ConnectionMode.PASSIVE
            else timedelta(seconds=interval)
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            always_update=False,
            update_interval=update_interval,
            update_method=None,
        )
        self.data = {
            "belt_state": BeltState.OFF,
            "speed": 0.0,
            "mode": WalkingPadMode.MANUAL,
            "session_running_time": 0,
            "session_distance": 0,
            "session_steps": 0,
            "status_timestamp": 0,
        }
        self._reconnect_lock = asyncio.Lock()

    def _refresh_should_run(self) -> bool:
        """Return True when periodic status polling is enabled."""
        return self.connection_mode != ConnectionMode.PASSIVE

    @property
    def status_reporting_enabled(self) -> bool:
        """Return True when sensors have an active status source."""
        return self._refresh_should_run()

    def _apply_update_interval(self) -> None:
        """Enable or disable the periodic refresh based on mode."""
        if self._refresh_should_run():
            self.update_interval = timedelta(
                seconds=self.status_update_interval_seconds
            )
        else:
            self.update_interval = None

    async def _async_persist_options(self) -> None:
        """Write connection mode and interval into the config entry options."""
        new_options = {
            **self.config_entry.options,
            CONF_CONNECTION_MODE: self.connection_mode.value,
            CONF_STATUS_UPDATE_INTERVAL: self.status_update_interval_seconds,
        }
        self.hass.config_entries.async_update_entry(
            self.config_entry, options=new_options
        )

    def _offline_status(self) -> WalkingPadStatus:
        """Return status for a powered-off / unreachable pad."""
        _LOGGER.debug("WalkingPad unreachable; setting state to off")
        return {
            **self.data,
            "belt_state": BeltState.OFF,
            "speed": 0.0,
        }

    async def _async_fall_back_to_polling(self, reason: str) -> WalkingPadStatus:
        """Leave persistent mode after a failure and free the remote."""
        if self.connection_mode == ConnectionMode.PERSISTENT:
            _LOGGER.warning("%s; falling back to polling connection mode", reason)
            self.connection_mode = ConnectionMode.POLLING
            self.walkingpad_device.connection_mode = ConnectionMode.POLLING
            self._apply_update_interval()
            await self._async_persist_options()
            self.async_update_listeners()
        return self._offline_status()

    @callback
    def _async_on_device_disconnected(self) -> None:
        """Handle an unexpected BLE disconnect while persistent mode is on."""
        self.hass.async_create_task(self._async_handle_unexpected_disconnect())

    async def _async_handle_unexpected_disconnect(self) -> None:
        """Fall back from persistent and publish offline status after a link drop."""
        # Polling intentionally disconnects after each poll.
        if self.connection_mode != ConnectionMode.PERSISTENT:
            self.async_update_listeners()
            return
        status = await self._async_fall_back_to_polling(
            "WalkingPad BLE link disconnected"
        )
        self.async_set_updated_data(status)

    async def _async_update_data(self) -> WalkingPadStatus:
        if not self._refresh_should_run():
            return self.data

        # Fast path: pad is not advertising (powered off / out of range).
        if (
            not self.connected
            and not self.walkingpad_device.is_currently_visible()
        ):
            if self.connection_mode == ConnectionMode.PERSISTENT:
                return await self._async_fall_back_to_polling(
                    "WalkingPad not visible while persistent"
                )
            return self._offline_status()

        previous_timestamp = self.data.get("status_timestamp", 0)

        try:
            async with asyncio.timeout(STATUS_UPDATE_TIMEOUT_SECONDS):
                if self.connection_mode == ConnectionMode.PERSISTENT:
                    try:
                        await self.walkingpad_device.update_state()
                    except Exception:  # pylint: disable=broad-except
                        return await self._async_fall_back_to_polling(
                            "Unable to update WalkingPad status"
                        )
                    if not self.connected:
                        return await self._async_fall_back_to_polling(
                            "Unable to connect to WalkingPad"
                        )
                    return self.data

                # Connect-on-demand: connect → ask stats → wait for notify → disconnect.
                try:
                    await self.walkingpad_device.update_state()
                    if self.connected:
                        await asyncio.sleep(STATUS_NOTIFICATION_WAIT_SECONDS)
                    else:
                        return self._offline_status()
                finally:
                    if self.connection_mode != ConnectionMode.PERSISTENT:
                        await self.walkingpad_device.disconnect()

                if self.data.get("status_timestamp", 0) <= previous_timestamp:
                    return self._offline_status()
                return self.data
        except TimeoutError:
            _LOGGER.warning(
                "WalkingPad status update timed out; treating device as offline"
            )
            try:
                await self.walkingpad_device.disconnect()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.debug("Disconnect after timeout failed", exc_info=True)
            if self.connection_mode == ConnectionMode.PERSISTENT:
                return await self._async_fall_back_to_polling(
                    "WalkingPad status update timed out"
                )
            return self._offline_status()
        except Exception:  # pylint: disable=broad-except
            _LOGGER.warning("WalkingPad status update failed", exc_info=True)
            with contextlib.suppress(Exception):
                await self.walkingpad_device.disconnect()
            if self.connection_mode == ConnectionMode.PERSISTENT:
                return await self._async_fall_back_to_polling(
                    "WalkingPad status update failed"
                )
            return self._offline_status()

    @property
    def connected(self) -> bool:
        """Get the device connection status."""
        return self.walkingpad_device.connected

    async def async_set_connection_mode(self, mode: ConnectionMode) -> None:
        """Persist and apply a connection mode."""
        if mode == self.connection_mode:
            if mode == ConnectionMode.PERSISTENT and not self.connected:
                await self.walkingpad_device.connect()
                if not self.connected:
                    await self._async_fall_back_to_polling(
                        "Unable to connect to WalkingPad"
                    )
                    self.async_set_updated_data(self._offline_status())
            return

        previous = self.connection_mode
        self.connection_mode = mode
        self.walkingpad_device.connection_mode = mode
        self._apply_update_interval()
        await self._async_persist_options()
        _LOGGER.debug("Connection mode set to %s (was %s)", mode, previous)

        if mode == ConnectionMode.PERSISTENT:
            await self.walkingpad_device.connect()
            if not self.connected:
                status = await self._async_fall_back_to_polling(
                    "Unable to connect to WalkingPad"
                )
                self.async_set_updated_data(status)
                return
            await self.async_request_refresh()
        elif mode == ConnectionMode.POLLING:
            if previous == ConnectionMode.PERSISTENT:
                await self.walkingpad_device.disconnect()
            if self._listeners:
                await self.async_request_refresh()
        else:  # PASSIVE
            await self.walkingpad_device.disconnect()

        self.async_update_listeners()

    async def async_set_status_update_interval(self, seconds: int) -> None:
        """Set the status polling interval in seconds."""
        seconds = max(1, int(seconds))
        if self.status_update_interval_seconds == seconds:
            self._apply_update_interval()
            return

        self.status_update_interval_seconds = seconds
        self._apply_update_interval()
        await self._async_persist_options()
        _LOGGER.debug("Status update interval set to %s seconds", seconds)
        self.async_update_listeners()

    async def async_try_reconnect_persistent(self) -> None:
        """Attempt a reconnect when an advertisement is seen in persistent mode."""
        if self.connection_mode != ConnectionMode.PERSISTENT or self.connected:
            return
        if self._reconnect_lock.locked():
            return
        async with self._reconnect_lock:
            if self.connection_mode != ConnectionMode.PERSISTENT or self.connected:
                return
            _LOGGER.debug("Advertisement seen; attempting persistent reconnect")
            await self.walkingpad_device.connect()
            if self.connected:
                await self.async_request_refresh()
            else:
                status = await self._async_fall_back_to_polling(
                    "Unable to reconnect to WalkingPad"
                )
                self.async_set_updated_data(status)

    @callback
    def _async_handle_update(self, status: WalkingPadStatus) -> None:
        """Receive status updates from the WalkingPad controller."""
        if status.get("status_timestamp", 0) > self.data.get("status_timestamp", 0):
            _LOGGER.debug("WalkingPad status update : %s", status)
            self.async_set_updated_data(status)

    async def async_shutdown(self) -> None:
        """Disconnect and shut down the coordinator."""
        await self.walkingpad_device.disconnect()
        await super().async_shutdown()
