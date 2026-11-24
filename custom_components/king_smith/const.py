"""Constants for the walkingpad integration."""

from enum import Enum, IntEnum, StrEnum, unique
from typing import Final, TypedDict

DOMAIN = "king_smith"


CONF_REMOTE_CONTROL: Final = "remote_control"
CONF_REMOTE_CONTROL_ENABLED: Final = "remote_control_enabled"
CONF_MAC: Final = "mac"
CONF_NAME: Final = "name"
CONF_PREFERRED_MODE: Final = "preferred_mode"
CONF_CONNECTION_MODE: Final = "connection_mode"
CONF_STATUS_UPDATE_INTERVAL: Final = "status_update_interval"


@unique
class BeltState(IntEnum):
    """An enumeration of the possible belt states."""

    OFF = -1  # device unreachable / powered off (not reported by the pad)
    STOPPED = 0
    ACTIVE = 1
    STANDBY = 5
    STARTING = 9
    UNKNOWN = 1000


@unique
class WalkingPadMode(Enum):
    """An enumeration of the possible WalkingPad modes."""

    AUTO = 0
    MANUAL = 1
    STANDBY = 2


class ConnectionMode(StrEnum):
    """How the integration uses the WalkingPad's single BLE connection."""

    POLLING = "polling"
    PERSISTENT = "persistent"
    PASSIVE = "passive"


DEFAULT_PREFERRED_MODE: Final = WalkingPadMode.MANUAL.name.lower()
PREFERRED_MODE_OPTIONS: Final = [
    WalkingPadMode.AUTO.name.lower(),
    WalkingPadMode.MANUAL.name.lower(),
]

DEFAULT_CONNECTION_MODE: Final = ConnectionMode.POLLING
CONNECTION_MODE_OPTIONS: Final = [mode.value for mode in ConnectionMode]

DEFAULT_STATUS_UPDATE_SECONDS: Final = 60


def parse_connection_mode(value: object | None) -> ConnectionMode:
    """Parse a stored connection mode, defaulting to polling."""
    if value is None:
        return DEFAULT_CONNECTION_MODE
    try:
        return ConnectionMode(str(value))
    except ValueError:
        return DEFAULT_CONNECTION_MODE


def migrate_connection_mode_from_legacy(
    stay_connected: bool | None,
    auto_status_updates: bool | None,
) -> ConnectionMode:
    """Map legacy Connected/Auto booleans to a connection mode."""
    if stay_connected:
        return ConnectionMode.PERSISTENT
    if auto_status_updates is True:
        return ConnectionMode.POLLING
    if auto_status_updates is False:
        return ConnectionMode.PASSIVE
    return DEFAULT_CONNECTION_MODE

# Optimistic belt/mode UI after a command, until a real status arrives.
TEMPORARY_STATE_EXPIRY_SECONDS: Final = 5

# Legacy entity unique-id suffixes (removed after connection-mode select).
LEGACY_CONNECTED_KEY: Final = "walkingpad_connected"
LEGACY_AUTO_STATUS_UPDATES_KEY: Final = "walkingpad_auto_status_updates"


class WalkingPadStatus(TypedDict):
    """A type to represent the state of the WalkingPad at a specific time."""

    belt_state: BeltState
    speed: float  # speed in km/h
    mode: WalkingPadMode
    session_running_time: int  # in seconds
    session_distance: int  # distance in meters
    session_steps: int
    status_timestamp: float
