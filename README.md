# Walkingpad - Home Assistant custom integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

Fork of [madmatah/hass-walkingpad](https://github.com/madmatah/hass-walkingpad) with connect-on-demand BLE control so the physical remote (and other clients) can share the WalkingPad’s single Bluetooth connection.

For FTMS / newer KingSmith protocols, see also [mcdax/hass-walkingpad](https://github.com/mcdax/hass-walkingpad).

---

**This integration sets up the following platforms.**

Platform | Description
-- | --
`binary_sensor` | **Connection status** — whether Home Assistant currently holds the BLE link.
`sensor` | WalkingPad usage metrics (distance, steps, duration, speed, state, mode).
`select` | **Connection mode** (`polling` / `persistent` / `passive`).
`number` | **Update interval** (seconds), plus optional speed control in manual mode (when HA remote control is enabled).
`switch` | Optional belt control (when HA remote control is enabled).

## Installation

### HACS
1. Open the HACS dashboard then click `Integrations`
1. Click the `3 dots menu` on the top right corner
1. Click `Custom repository`
1. Enter the repo url `https://github.com/KrilYura/hass-walkingpad`
1. Choose the `Integration` category then **Submit**
1. Click on the new `Kingsmith WalkingPad` repo
1. Click on `Download` on the bottom right corner
1. Restart Home Assistant

### Manual
1. Open the directory for your HA configuration (where you find `configuration.yaml`)
1. If there is no `custom_components` directory, create it
1. In `custom_components` create a folder called `king_smith`
1. Copy all files from `custom_components/king_smith/` in this repository into that folder
1. Restart Home Assistant
1. In the HA UI go to **Settings → Devices & services**, click **Add integration**, and search for **WalkingPad**

## Configuration

You need a Bluetooth adapter or an ESPHome Bluetooth proxy. See the official [Bluetooth](https://www.home-assistant.io/integrations/bluetooth/) docs.

Before pairing/discovery, make sure nothing else is connected to the WalkingPad (phone app, another HA instance, etc.).

The WalkingPad accepts **only one BLE client at a time**. While this integration holds the link, the hand remote and KS Fit cannot connect.

### 1. Automatic bluetooth discovery

If the pad’s BLE name matches a known pattern, Home Assistant can discover it under **Settings → Devices & services**.

![Discovered device](./assets/images/discovered-device.png)

Configure it and give it a friendly name:

![Automatic config flow](./assets/images/bluetooth-config-flow.png)

If it is not discovered, use manual configuration (see [FAQ](#my-walkingpad-device-is-not-detected)).

### 2. Manual configuration

**Settings → Devices & services → Add integration → KingSmith WalkingPad**

![Manual configuration](./assets/images/manual-config-flow.png)

Enter the MAC address and a friendly name.

Setup can succeed even if the pad is powered off; the integration connects later when the pad is available.

### 3. Connection mode

The WalkingPad’s single BLE slot is managed by one **Connection mode** select (default `polling`) and an **Update interval** number (default `60` seconds). The next poll starts after the previous one finishes, plus this interval.

| Mode | Behaviour | Hand remote | Connection status |
| --- | --- | --- | --- |
| **Polling** | Each cycle: connect → read status → disconnect → wait interval | Free between polls | Briefly on during each poll |
| **Persistent** | Keeps a BLE connection and polls status on the interval | Blocked while linked | On while the link is held |
| **Passive** | No polling; sensors unavailable | Free | Off |

If **Persistent** cannot connect, the link drops, or a status update times out, the mode falls back to **Polling** so the remote can be used again.

In **Polling** and **Passive**, Home Assistant remote-control actions (start/stop/speed/mode) also use connect-on-demand: connect → send the command → disconnect. The hand remote is free again afterward. **Persistent** keeps the link for those commands as well.

**State** sensor values include `off` when the pad is unreachable. Other metrics go unavailable while state is `off`. In **Passive** mode, all sensors are unavailable.

### 4. Remote control (from Home Assistant)

Optional HA start/stop/speed control (not the physical remote). **Disabled by default** for safety.

Enable it during setup (expand **Remote control**) or later via the integration **Configure** menu, then choose a preferred mode:

#### Manual mode (default)

- Belt **switch**: on starts the belt, off stops it
- Speed **number**: 0.5–6.0 km/h in 0.1 steps (only while the belt is active or starting)

#### Auto mode

- Switch selects WalkingPad **AUTO** vs **STANDBY**
- No speed entity (the pad adjusts speed from motion)

**Safety:** keep the belt area clear. Use at your own risk.

## FAQ

### My WalkingPad device is not detected

Make sure no other Bluetooth client is connected to the pad.

If automatic discovery still fails, the BLE name may be unknown — add it manually.

Scan for the MAC address, for example on Linux:

```
$> sudo hcitool lescan

LE Scan ...
85:AA:BB:CC:DD:FF KS-ST-A1P
85:AA:BB:CC:EE:FF KS-ST-A1P
```

Then **Settings → Devices & services → Add integration → Kingsmith Walkingpad**, enter the MAC and a name.

If it works, open an issue with the Bluetooth name and model so discovery can be extended.

### The hand remote stops working

The pad allows one BLE connection. Set **Connection mode** to **Polling** or **Passive**. **Persistent** blocks the remote while Home Assistant holds the link.

### Sensors stay on old values after I power the pad off

Unreachable pads should move **State** to `off` and mark other sensors unavailable within about one update interval (when not in **Passive** mode).

## FAQ for developers

### How to enable my bluetooth adapter in the devcontainer ?

Pointers for a Linux host (see also the [Home Assistant Bluetooth page](https://www.home-assistant.io/integrations/bluetooth#additional-details-for-container-core-and-supervised-installs)):

#### 1. Install and enable DBus-Broker

```
sudo apt install dbus-broker
sudo systemctl enable dbus-broker.service
sudo systemctl --global enable dbus-broker.service

reboot
```

#### 2. Ensure that bluez is installed

Bluez >= 5.63 on the host.

#### 3. Ensure that your dbus socket is in /run/dbus

Otherwise tweak `.devcontainer.json` (`runArgs`).

#### 4. Profit

Run the devcontainer and start Home Assistant with `scripts/develop`. A TLS error on the first run is common — restart the command once.

## Acknowledgements

Based on [madmatah/hass-walkingpad](https://github.com/madmatah/hass-walkingpad).

Uses [ph4-walkingpad](https://github.com/ph4r05/ph4-walkingpad) ([@ph4r05](https://github.com/ph4r05)).

Inspired by [@indiefan](https://github.com/indiefan)’s [king_smith](https://github.com/indiefan/king_smith) integration.

***

[commits-shield]: https://img.shields.io/github/commit-activity/y/KrilYura/hass-walkingpad.svg?style=for-the-badge
[commits]: https://github.com/KrilYura/hass-walkingpad/commits/main
[license-shield]: https://img.shields.io/github/license/KrilYura/hass-walkingpad.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/KrilYura/hass-walkingpad.svg?style=for-the-badge
[releases]: https://github.com/KrilYura/hass-walkingpad/releases
