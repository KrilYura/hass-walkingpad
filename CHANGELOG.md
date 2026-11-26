# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic
Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.2-yk] - 2026-11-27

### Changed

- clarify README that Polling/Passive HA remote-control actions use connect-on-demand (connect → command → disconnect)

### Fixed

- CI unit tests always load Home Assistant stubs so GitHub Actions can run without installing HA

## [0.4.1-yk] - 2026-11-25

### Added

- **Connection status** binary sensor reflecting the live BLE link (briefly on during polling; tracks the held link in persistent mode)

## [0.4.0-yk] - 2026-11-24

### Changed

- replace Connected / Auto status updates switches with a single **Connection mode** select (`polling` / `persistent` / `passive`)
- persist connection mode and update interval in config entry options
- fall back from persistent to polling when connect fails, the link drops, or a status update times out
- manual setup no longer requires the pad to be advertising (scanner still required)

### Fixed

- serialize BLE connect / disconnect / commands with a real session lock
- surface command failures to the UI instead of silently no-oping
- belt optimistic state expiry no longer tied to the poll interval
- make `connect()` idempotent when already connected
- config entry unique id always uses a formatted MAC address
- duration sensors use `duration` device class; mode sensor state translations

### Added

- unit tests for connection-mode migration and coordinator behaviour

## [0.3.6-yk] - 2026-11-24

### Fixed

- turn Connected off when the BLE link drops or status updates time out while stay-connected

## [0.3.5-yk] - 2026-11-24

### Fixed

- detect powered-off pad promptly (skip stale BLE cache connects; treat update timeouts as offline)

## [0.3.4-yk] - 2026-11-24

### Changed

- all sensors unavailable when Connected and Auto status updates are both off
- Connected switch turns back off if enabling it fails to connect

## [0.3.3-yk] - 2026-11-24

### Changed

- Auto status updates switch is unavailable while Connected is on
- State reports off when the pad is unreachable; other sensors become unavailable

## [0.3.2-yk] - 2026-11-24

### Fixed

- allow integration setup when the WalkingPad is powered off / not advertising

## [0.3.1-yk] - 2026-11-24

### Added

- Update interval number entity (positive integer, seconds) to configure status polling

## [0.3.0-yk] - 2026-11-24

### Added

- Connected switch to keep or release the BLE link (off frees the remote / other clients)
- Auto status updates switch for connect → status → disconnect polling when Connected is off (1 minute interval)

### Fixed

- link sensor, switch, and number entities to the WalkingPad device registry entry

## [0.3.0] - 2025-11-15

### Added

- remote control configuration options
- new sensors (walkingpad_state and walkingpad_mode)
- belt control switch
- speed control

## [0.2.1] - 2025-08-08

### Changed

- upgrade homeassistant to 2025.8.0
- upgrade ph4-walkingpad to 1.0.2

### Fixed

- error when using this integration with latest versions of bleak

## [0.2.0] - 2025-02-23

### Changed

- add support for more WalkingPad models
- upgrade homeassistant to 2025.2.5

### Fixed

- warnings about invalid suggested_unit_of_measurement
- add missing translations for sensor names
- handle unknown belt states

## [0.1.0] - 2024-03-29

### Added

- support for WalkingPad A1 Pro
- manual config flow
- bluetooth discovery config flow
- distance sensor
- steps sensor
- duration sensors (available in several units : minutes, hours, days)
- current speed sensor
- basic configuration guide in the README

[unreleased]: https://github.com/KrilYura/hass-walkingpad/compare/0.4.2-yk...HEAD
[0.4.2-yk]: https://github.com/KrilYura/hass-walkingpad/compare/0.4.1-yk...0.4.2-yk
[0.4.1-yk]: https://github.com/KrilYura/hass-walkingpad/compare/0.4.0-yk...0.4.1-yk
[0.4.0-yk]: https://github.com/KrilYura/hass-walkingpad/compare/0.3.6-yk...0.4.0-yk
[0.3.6-yk]: https://github.com/KrilYura/hass-walkingpad/compare/0.3.5-yk...0.3.6-yk
[0.3.5-yk]: https://github.com/KrilYura/hass-walkingpad/compare/0.3.4-yk...0.3.5-yk
[0.3.4-yk]: https://github.com/KrilYura/hass-walkingpad/compare/0.3.3-yk...0.3.4-yk
[0.3.3-yk]: https://github.com/KrilYura/hass-walkingpad/compare/0.3.2-yk...0.3.3-yk
[0.3.2-yk]: https://github.com/KrilYura/hass-walkingpad/compare/0.3.1-yk...0.3.2-yk
[0.3.1-yk]: https://github.com/KrilYura/hass-walkingpad/compare/0.3.0-yk...0.3.1-yk
[0.3.0-yk]: https://github.com/KrilYura/hass-walkingpad/compare/v0.3.0...0.3.0-yk
[0.3.0]: https://github.com/madmatah/hass-walkingpad/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/madmatah/hass-walkingpad/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/madmatah/hass-walkingpad/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/madmatah/hass-walkingpad/compare/eb2749688ebbf334fa29c5004511e8ee8680307f...v0.1.0
