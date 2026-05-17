# esp32cam-stream HA Integration

A Home Assistant custom integration for
[esp32cam-stream](https://github.com/atkitimo07/esp32cam-stream) cameras.

The integration exposes the camera stream through go2rtc, controls the camera's
night vision and IR LED endpoints, reports device diagnostics, and can
automatically control night vision/IR from image analysis.

## Features

- Config flow setup and reconfiguration from the Home Assistant UI.
- Home Assistant camera entity backed by a go2rtc MJPEG stream.
- Camera snapshots through go2rtc.
- Manual night vision switch.
- Brightness-capable IR LED light entity.
- Manual IR LED behavior that enables night vision first.
- Night vision off behavior that also turns the IR LED off.
- Diagnostic sensors for FPS, RSSI, temperature, and image analysis metrics.
- Image-based automatic night vision and IR LED control.
- Restore-backed automatic control switches and tuning numbers.

## Requirements

- [esp32cam-stream](https://github.com/atkitimo07/esp32cam-stream)
- [go2rtc](https://github.com/AlexxIT/go2rtc)
- Home Assistant with custom integrations enabled
- Python packages declared by the integration:
  - `aiohttp`
  - `Pillow`

## Installation

Copy the integration directory into your Home Assistant custom components
directory:

```text
custom_components/esp32cam_stream_integration
```

Restart Home Assistant, then add the integration from:

```text
Settings > Devices & services > Add integration
```

## Configuration

The setup form asks for:

- Name: the display name for the camera/device.
- Camera host: the base URL or host for the esp32cam-stream device.
- go2rtc URL: the go2rtc base URL. Defaults to `http://localhost:1984`.
- go2rtc camera name: the go2rtc stream name. If left blank, the integration
  uses the configured Name.

The go2rtc URL and camera name can also be changed later from the integration's
options or reconfigure flow.

## go2rtc Usage

The camera entity uses go2rtc for the live MJPEG stream:

```text
/api/stream.mjpeg?src=<go2rtc camera name>
```

Home Assistant camera snapshots and automatic image analysis use go2rtc JPEG
frames:

```text
/api/frame.jpeg?src=<go2rtc camera name>
```

The esp32cam-stream device is still used directly for control and status
endpoints such as:

```text
/status
/nightvision/state
/nightvision?state=0|1
/irled/state
/irled?state=<brightness>
```

## Entities

The integration creates a single Home Assistant device per configured camera.

Camera:

- Camera stream and snapshot entity

Light:

- IR LED: brightness-capable light entity. Brightness is mapped to the camera's
  `irled` state from `0.0` to `1.0`.

Switches:

- Night Vision
- Auto Night Vision
- Auto IR LED

Sensors:

- FPS
- RSSI
- Temperature
- Image Mean Luminance
- Image Median Luminance
- Image P25 Luminance
- Image Pink Index
- Image Pink Pixels

Binary sensors:

- Night Vision Image Dark
- IR LED Image Dark

Numbers:

- Image Analysis Interval
- Night Vision On Threshold
- Night Vision Pink Pixels Off Threshold
- IR LED On Threshold
- IR LED Pink Pixels Off Threshold
- IR LED Auto Brightness

## Manual Controls

The Night Vision switch calls the camera's night vision endpoint directly.
Turning Night Vision off also turns the IR LED off so the two outputs stay in a
valid state.

The IR LED light entity supports brightness. Turning the IR LED on manually
enables night vision first if night vision is not already enabled.

## Automatic Night Vision And IR LED Control

This integration can analyze periodic snapshots from go2rtc and use the image
metrics to control night vision and the IR LED.

The automatic control is intentionally two-pass:

1. The integration enables night vision when the image is dark enough.
2. On a later snapshot, if night vision is already enabled and the image is
   still dark enough, the integration enables the IR LED.

The IR LED is never automatically enabled unless night vision is already on. If
night vision is turned off, the integration also turns the IR LED off.

Snapshots for image analysis are fetched from go2rtc:

```text
/api/frame.jpeg?src=<go2rtc camera name>
```

## Image Analysis Sensors

The integration exposes diagnostic sensors to help tune automatic control:

- Image Mean Luminance
- Image Median Luminance
- Image P25 Luminance
- Image Pink Index
- Image Pink Pixels

Automatic turn-on decisions use Image P25 Luminance, which is less sensitive to
isolated bright areas than a full-frame average. Automatic turn-off decisions use
Image Pink Pixels so the lights are switched off when the IR/pink cast falls
below the configured threshold.

## Automatic Control Entities

The following configuration switches enable or disable automatic behavior:

- Auto Night Vision
- Auto IR LED

The following number entities tune the control loop:

- Image Analysis Interval
- Night Vision On Threshold
- Night Vision Pink Pixels Off Threshold
- IR LED On Threshold
- IR LED Pink Pixels Off Threshold
- IR LED Auto Brightness

The on thresholds are luminance values. The off thresholds are Image Pink Pixels
percentages.

Default values:

- Image Analysis Interval: `30` seconds
- Night Vision On Threshold: `10`
- Night Vision Pink Pixels Off Threshold: `80%`
- IR LED On Threshold: `20`
- IR LED Pink Pixels Off Threshold: `98%`
- IR LED Auto Brightness: `1%`

Automatic control switches and tuning numbers are restored by Home Assistant, so
the last configured values are reused after restart.

## Availability And Polling

The coordinator polls status, IR LED state, and night vision state every five
seconds. The device remains available through brief endpoint failures and is
marked unavailable after repeated polling failures.

Image analysis runs on its own configurable interval and reuses the previous
analysis result between captures.
