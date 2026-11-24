"""The Walking Pad Coordinator."""

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, BeltState, WalkingPadMode, WalkingPadStatus
from .walkingpad import WalkingPad

_LOGGER = logging.getLogger(__name__)

DEFAULT_STATUS_UPDATE_SECONDS = 60

# Connect can take up to ~10s; leave room for ask_stats + disconnect.
STATUS_UPDATE_TIMEOUT_SECONDS = 20

# Wait for the status notification after ask_stats before releasing the BLE link.
STATUS_NOTIFICATION_WAIT_SECONDS = 0.75


class WalkingPadCoordinator(DataUpdateCoordinator[WalkingPadStatus]):
    """WalkingPad coordinator."""

    def __init__(self, hass: HomeAssistant, walkingpad_device: WalkingPad) -> None:
        """Initialise WalkingPad coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            always_update=False,
            update_interval=timedelta(seconds=DEFAULT_STATUS_UPDATE_SECONDS),
            update_method=None,
        )
        self.walkingpad_device = walkingpad_device
        self.walkingpad_device.register_status_callback(self._async_handle_update)
        self.walkingpad_device.register_disconnect_callback(
            self._async_on_device_disconnected
        )
        self.stay_connected = True
        self.auto_status_updates = True
        self.status_update_interval_seconds = DEFAULT_STATUS_UPDATE_SECONDS
        self.walkingpad_device.stay_connected = True
        self.data = {
            "belt_state": BeltState.OFF,
            "speed": 0.0,
            "mode": WalkingPadMode.MANUAL,
            "session_running_time": 0,
            "session_distance": 0,
            "session_steps": 0,
            "status_timestamp": 0,
        }

    def _refresh_should_run(self) -> bool:
        """Return True when periodic status polling is enabled."""
        return self.stay_connected or self.auto_status_updates

    @property
    def status_reporting_enabled(self) -> bool:
        """Return True when sensors have an active status source."""
        return self._refresh_should_run()

    def _apply_update_interval(self) -> None:
        """Enable or disable the periodic refresh based on toggle state."""
        if self._refresh_should_run():
            self.update_interval = timedelta(
                seconds=self.status_update_interval_seconds
            )
        else:
            self.update_interval = None

    def _offline_status(self) -> WalkingPadStatus:
        """Return status for a powered-off / unreachable pad."""
        _LOGGER.debug("WalkingPad unreachable; setting state to off")
        return {
            **self.data,
            "belt_state": BeltState.OFF,
            "speed": 0.0,
        }

    async def _async_mark_unreachable(self) -> WalkingPadStatus:
        """Apply offline status and drop stay-connected when the link is lost."""
        if self.stay_connected:
            await self._async_revert_stay_connected()
        return self._offline_status()

    @callback
    def _async_on_device_disconnected(self) -> None:
        """Handle an unexpected BLE disconnect while Connected is on."""
        self.hass.async_create_task(self._async_handle_unexpected_disconnect())

    async def _async_handle_unexpected_disconnect(self) -> None:
        """Revert Connected and publish offline status after a link drop."""
        status = await self._async_mark_unreachable()
        self.async_set_updated_data(status)

    async def _async_update_data(self) -> WalkingPadStatus:
        if not self._refresh_should_run():
            return self.data

        # Fast path: pad is not advertising (powered off / out of range).
        if (
            not self.connected
            and not self.walkingpad_device.is_currently_visible()
        ):
            return await self._async_mark_unreachable()

        try:
            async with asyncio.timeout(STATUS_UPDATE_TIMEOUT_SECONDS):
                if self.stay_connected:
                    await self.walkingpad_device.update_state()
                    if not self.connected:
                        return await self._async_mark_unreachable()
                    return self.data

                # Connect-on-demand: connect → ask stats → wait for notify → disconnect.
                try:
                    await self.walkingpad_device.update_state()
                    if self.connected:
                        await asyncio.sleep(STATUS_NOTIFICATION_WAIT_SECONDS)
                    else:
                        return self._offline_status()
                finally:
                    if not self.stay_connected:
                        await self.walkingpad_device.disconnect()
                return self.data
        except TimeoutError:
            _LOGGER.warning(
                "WalkingPad status update timed out; treating device as offline"
            )
            try:
                await self.walkingpad_device.disconnect()
            except Exception:  # pylint: disable=broad-except
                pass
            return await self._async_mark_unreachable()

    @property
    def connected(self) -> bool:
        """Get the device connection status."""
        return self.walkingpad_device.connected

    async def _async_revert_stay_connected(self) -> None:
        """Turn stay-connected off after a failed connection attempt."""
        _LOGGER.warning(
            "Unable to connect to WalkingPad; turning Connected off"
        )
        self.stay_connected = False
        self.walkingpad_device.stay_connected = False
        self._apply_update_interval()
        self.async_update_listeners()

    async def async_set_stay_connected(self, enabled: bool) -> None:
        """Persist the stay-connected preference and apply it."""
        if not enabled:
            if not self.stay_connected:
                return
            self.stay_connected = False
            self.walkingpad_device.stay_connected = False
            self._apply_update_interval()
            _LOGGER.debug("Stay connected set to False")
            await self.walkingpad_device.disconnect()
            if self.auto_status_updates:
                await self.async_request_refresh()
            self.async_update_listeners()
            return

        # Enabling stay-connected: connect now, otherwise revert to off.
        self.stay_connected = True
        self.walkingpad_device.stay_connected = True
        self._apply_update_interval()
        _LOGGER.debug("Stay connected set to True")

        await self.walkingpad_device.connect()
        if not self.connected:
            await self._async_revert_stay_connected()
            return

        await self.async_request_refresh()
        self.async_update_listeners()

    async def async_set_auto_status_updates(self, enabled: bool) -> None:
        """Persist the auto status updates preference and apply it."""
        if self.auto_status_updates == enabled:
            return

        self.auto_status_updates = enabled
        self._apply_update_interval()
        _LOGGER.debug("Auto status updates set to %s", enabled)

        if enabled and not self.stay_connected and self._listeners:
            await self.async_request_refresh()

        self.async_update_listeners()

    async def async_set_status_update_interval(self, seconds: int) -> None:
        """Set the status polling interval in seconds."""
        seconds = max(1, int(seconds))
        if self.status_update_interval_seconds == seconds:
            self._apply_update_interval()
            return

        self.status_update_interval_seconds = seconds
        self._apply_update_interval()
        _LOGGER.debug("Status update interval set to %s seconds", seconds)
        self.async_update_listeners()

    @callback
    def _async_handle_update(self, status: WalkingPadStatus) -> None:
        """Receive status updates from the WalkingPad controller."""
        if status.get("status_timestamp", 0) > self.data.get("status_timestamp", 0):
            _LOGGER.debug("WalkingPad status update : %s", status)
            self.async_set_updated_data(status)

    @callback
    def _async_handle_disconnect(self) -> None:
        """Trigger the callbacks for disconnected."""
        self.async_update_listeners()

    async def _async_connect(self, *_) -> None:
        """Connect to the device when stay-connected mode is enabled."""
        if self.stay_connected:
            await self.walkingpad_device.connect()

    async def _async_disconnect(self, *_) -> None:
        """Disconnect the device."""
        await self.walkingpad_device.disconnect()

    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        """Optionally connect the device and listen for data updates."""
        if not self._listeners and self.stay_connected:
            async_call_later(
                self.hass,
                0,
                HassJob(self._async_connect, "Connect to WalkingPad"),
            )
        return super().async_add_listener(update_callback, context)

    @callback
    def _unschedule_refresh(self) -> None:
        """Unschedule any pending refresh since there is no longer any listeners."""
        async_call_later(
            self.hass,
            0,
            HassJob(self._async_disconnect, "Disonnect the WalkingPad"),
        )
        return super()._unschedule_refresh()
