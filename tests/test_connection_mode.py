"""Unit tests for connection mode helpers."""

from custom_components.king_smith.const import (
    ConnectionMode,
    migrate_connection_mode_from_legacy,
    parse_connection_mode,
)


def test_parse_connection_mode_valid() -> None:
    """Valid strings map to enum members."""
    assert parse_connection_mode("polling") is ConnectionMode.POLLING
    assert parse_connection_mode("persistent") is ConnectionMode.PERSISTENT
    assert parse_connection_mode("passive") is ConnectionMode.PASSIVE


def test_parse_connection_mode_defaults() -> None:
    """Invalid or missing values default to polling."""
    assert parse_connection_mode(None) is ConnectionMode.POLLING
    assert parse_connection_mode("nope") is ConnectionMode.POLLING


def test_migrate_from_legacy_connected() -> None:
    """Connected on maps to persistent regardless of Auto."""
    assert (
        migrate_connection_mode_from_legacy(True, True) is ConnectionMode.PERSISTENT
    )
    assert (
        migrate_connection_mode_from_legacy(True, False) is ConnectionMode.PERSISTENT
    )
    assert (
        migrate_connection_mode_from_legacy(True, None) is ConnectionMode.PERSISTENT
    )


def test_migrate_from_legacy_auto_only() -> None:
    """Auto on with Connected off maps to polling."""
    assert (
        migrate_connection_mode_from_legacy(False, True) is ConnectionMode.POLLING
    )


def test_migrate_from_legacy_both_off() -> None:
    """Both off maps to passive."""
    assert (
        migrate_connection_mode_from_legacy(False, False) is ConnectionMode.PASSIVE
    )


def test_migrate_from_legacy_unknown() -> None:
    """Missing legacy state defaults to polling."""
    assert migrate_connection_mode_from_legacy(None, None) is ConnectionMode.POLLING
    assert migrate_connection_mode_from_legacy(False, None) is ConnectionMode.POLLING
