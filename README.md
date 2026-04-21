# FRA Betriebsrichtung for Home Assistant

[![version](https://img.shields.io/github/manifest-json/v/Orishas/fra_betriebsrichtung?filename=custom_components%2Ffra_betriebsrichtung%2Fmanifest.json&color=slateblue)](https://github.com/Orishas/fra_betriebsrichtung/releases/latest)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg?logo=HomeAssistantCommunityStore&logoColor=white)](https://www.hacs.xyz/)
[![HACS validation](https://github.com/Orishas/fra_betriebsrichtung/actions/workflows/hacs.yml/badge.svg)](https://github.com/Orishas/fra_betriebsrichtung/actions/workflows/hacs.yml)
[![Hassfest](https://github.com/Orishas/fra_betriebsrichtung/actions/workflows/hassfest.yml/badge.svg)](https://github.com/Orishas/fra_betriebsrichtung/actions/workflows/hassfest.yml)

Home Assistant custom integration for the current and forecast operating
direction at Frankfurt Airport (FRA).

It helps you see whether the active or forecast operating direction is likely
to cause aircraft noise at your location.

## Features

1. Current FRA operating direction (`BR 07` or `BR 25`).
2. Forecast operating direction with dated forecast slots.
3. Local aircraft-noise binary sensor based on your configured noise direction.
4. Forecast aircraft-noise binary sensor for the next forecast slot.
5. Next forecast window that matches your local noise direction.
6. Direction-change event for automations.
7. Diagnostics with source health and fallback status.

The integration uses public HTML pages only. It does not use hidden or
undocumented API endpoints.

## Entities

| Entity | State | Purpose |
| --- | --- | --- |
| `sensor.fra_betriebsrichtung_aktuell` | `BR 07` / `BR 25` | Current operating direction |
| `sensor.fra_betriebsrichtung_forecast` | `BR 07` / `BR 25` | Next forecast direction |
| `binary_sensor.fra_betriebsrichtung_fluglaerm` | `on` / `off` | Current direction matches your configured noise direction |
| `binary_sensor.fra_betriebsrichtung_fluglaerm_forecast` | `on` / `off` | Next forecast slot matches your configured noise direction |
| `sensor.fra_betriebsrichtung_naechster_fluglaerm` | timestamp | Start of the next forecast slot matching your noise direction |

### Forecast slots

Forecast slots are exposed as attributes on
`sensor.fra_betriebsrichtung_forecast`.

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

Useful attributes include:

- `next_slot`
- `next_slot_label`
- `slots`
- `source`
- `last_update`
- `primary_ok`
- `fallback_ok`
- `fallback_used`
- `last_success`

## Installation

### HACS

1. Open HACS.
2. Add this repository as a custom repository:
   `https://github.com/Orishas/fra_betriebsrichtung`
3. Select category `Integration`.
4. Install `FRA Betriebsrichtung`.
5. Restart Home Assistant.
6. Add the integration from **Settings > Devices & services**.

The integration has also been submitted for the HACS default repository:
<https://github.com/hacs/default/pull/7175>

### Manual

Copy `custom_components/fra_betriebsrichtung` into your Home Assistant
configuration directory:

```text
config/custom_components/fra_betriebsrichtung
```

Restart Home Assistant and add the integration from the UI.

## Configuration

FRA Betriebsrichtung is configured from the Home Assistant UI.

1. Go to **Settings > Devices & services**.
2. Click **Add integration**.
3. Search for `FRA Betriebsrichtung`.
4. Select the operating direction that usually causes aircraft noise at your
   location:
   - `BR 07`
   - `BR 25`
5. Submit the setup dialog.

You can change the noise direction later from the integration options.

Only one config entry is supported.

## Events

The integration fires an event when the current operating direction changes:

```text
fra_betriebsrichtung_direction_changed
```

Event data:

- `old_direction`
- `new_direction`
- `noise_direction`
- `noise_active`
- `source`
- `last_update`
- `current_since`
- `next_slot`

The event is not fired during initial setup.

## Automation examples

### Notify when aircraft noise starts

```yaml
automation:
  - alias: "FRA aircraft noise active"
    trigger:
      - platform: state
        entity_id: binary_sensor.fra_betriebsrichtung_fluglaerm
        to: "on"
    action:
      - service: notify.mobile_app_phone
        data:
          message: "FRA operating direction now matches your local noise direction."
```

### Notify when the forecast predicts aircraft noise

```yaml
automation:
  - alias: "FRA aircraft noise forecast"
    trigger:
      - platform: state
        entity_id: binary_sensor.fra_betriebsrichtung_fluglaerm_forecast
        to: "on"
    action:
      - service: notify.mobile_app_phone
        data:
          message: >-
            FRA forecast matches your noise direction from
            {{ state_attr('sensor.fra_betriebsrichtung_forecast', 'next_slot')['from'] }}.
```

### React to direction changes

```yaml
automation:
  - alias: "FRA direction changed"
    trigger:
      - platform: event
        event_type: fra_betriebsrichtung_direction_changed
    action:
      - service: notify.mobile_app_phone
        data:
          message: >-
            FRA changed from {{ trigger.event.data.old_direction }} to
            {{ trigger.event.data.new_direction }}.
```

## Dashboard example

```yaml
type: entities
title: FRA Betriebsrichtung
entities:
  - entity: sensor.fra_betriebsrichtung_aktuell
  - entity: sensor.fra_betriebsrichtung_forecast
  - entity: binary_sensor.fra_betriebsrichtung_fluglaerm
  - entity: binary_sensor.fra_betriebsrichtung_fluglaerm_forecast
  - entity: sensor.fra_betriebsrichtung_naechster_fluglaerm
```

## Data sources

Primary source:

- <https://www.umwelthaus.org/fluglaerm/anwendungen-service/aktuelle-betriebsrichtung-und-prognose/>

Fallback source:

- <https://betriebsrichtungsprognose.de/frankfurt-fra/>

The integration polls every 30 minutes and prefers Umwelthaus. The fallback
source is used when primary data is incomplete or unavailable.

## Updates with HACS

HACS tracks GitHub releases for this repository. When a new release is
published, HACS can show it as an update in Home Assistant. Install the update
from HACS and restart Home Assistant so the updated Python code is loaded.

## Troubleshooting

- If the entities are unavailable, check the integration diagnostics from
  **Settings > Devices & services**.
- `fallback_used: true` means the primary source was incomplete and the
  fallback source supplied missing data.
- Website structures can change. Parser failures are handled gracefully, and the
  integration does not invent operating direction data.

## Acknowledgements

Thank you to the Umwelt- und Nachbarschaftshaus / Umwelthaus and to
betriebsrichtungsprognose.de for publishing operating direction information for
Frankfurt Airport.

This integration is not affiliated with, endorsed by, or officially connected to
those websites or their operators.
