# FRA Betriebsrichtung

Home Assistant custom integration for the current and forecast operating
direction at Frankfurt Airport (FRA).

The integration polls public HTML pages every 30 minutes and exposes:

- `sensor.fra_betriebsrichtung_aktuell`
- `sensor.fra_betriebsrichtung_forecast`
- `binary_sensor.fra_betriebsrichtung_fluglaerm`

## Data sources

Primary source:

- <https://www.umwelthaus.org/fluglaerm/anwendungen-service/aktuelle-betriebsrichtung-und-prognose/>

Fallback source:

- <https://betriebsrichtungsprognose.de/frankfurt-fra/>

The integration scrapes visible HTML only. It does not use hidden or
undocumented API endpoints.

## Installation with HACS

1. Open HACS.
2. Add this repository as a custom repository with category `Integration`.
3. Install `FRA Betriebsrichtung`.
4. Restart Home Assistant.
5. Add the integration from **Settings > Devices & services**.

## Manual installation

Copy `custom_components/fra_betriebsrichtung` into your Home Assistant
configuration directory:

```text
config/custom_components/fra_betriebsrichtung
```

Restart Home Assistant and add the integration from the UI.

## Setup

During UI setup, choose which operating direction normally causes aircraft noise
at your location:

- `BR 07`
- `BR 25`

You can change this later from the integration options.

## Entities

### Current operating direction

`sensor.fra_betriebsrichtung_aktuell`

State examples:

- `BR 07`
- `BR 25`

Attributes may include:

- `label`
- `source`
- `last_update`
- `current_since`

### Forecast operating direction

`sensor.fra_betriebsrichtung_forecast`

State is the next forecasted direction where available, otherwise a short
summary.

Attributes:

- `summary`
- `next_slot`
- `slots`
- `source`
- `last_update`

Forecast slots use this shape:

```json
[
  {
    "from": "06:00",
    "to": "14:00",
    "direction": "BR 25",
    "date": "2026-04-22",
    "start": "2026-04-22T06:00:00+02:00",
    "end": "2026-04-22T14:00:00+02:00"
  }
]
```

### Aircraft noise

`binary_sensor.fra_betriebsrichtung_fluglaerm`

This sensor is `on` when the current operating direction matches the direction
selected during setup.

Attributes:

- `noise_direction`
- `current_direction`
- `source`
- `last_update`

## Notes

Website structures can change. The parsers are defensive, but if both sources
cannot be parsed, the affected entities become unavailable instead of inventing
data.

## Updates with HACS

HACS tracks GitHub releases for this repository. When a new release is
published, HACS can show it as an update in Home Assistant. Install the update
from HACS and restart Home Assistant so the updated Python code is loaded.

## Acknowledgements

Thank you to the Umwelt- und Nachbarschaftshaus / Umwelthaus and to
betriebsrichtungsprognose.de for publishing operating direction information for
Frankfurt Airport. This integration is not affiliated with, endorsed by, or
officially connected to those websites or their operators.
