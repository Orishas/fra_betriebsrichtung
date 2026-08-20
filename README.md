# FRA Betriebsrichtung for Home Assistant

[![version](https://img.shields.io/github/manifest-json/v/Orishas/fra_betriebsrichtung?filename=custom_components%2Ffra_betriebsrichtung%2Fmanifest.json&color=slateblue)](https://github.com/Orishas/fra_betriebsrichtung/releases/latest)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg?logo=HomeAssistantCommunityStore&logoColor=white)](https://www.hacs.xyz/)
[![HACS validation](https://github.com/Orishas/fra_betriebsrichtung/actions/workflows/hacs.yml/badge.svg)](https://github.com/Orishas/fra_betriebsrichtung/actions/workflows/hacs.yml)
[![Hassfest](https://github.com/Orishas/fra_betriebsrichtung/actions/workflows/hassfest.yml/badge.svg)](https://github.com/Orishas/fra_betriebsrichtung/actions/workflows/hassfest.yml)

Home Assistant custom integration for the current and forecast operating
direction at Frankfurt Airport (FRA), with a noise indicator for your location.

## Entities

| Entity | Default UI name | State | Purpose |
| --- | --- | --- | --- |
| `sensor.fra_betriebsrichtung_current_direction` | Operating direction | `BR 07` / `BR 25` | Current operating direction |
| `sensor.fra_betriebsrichtung_forecast` | Forecast | `BR 07` / `BR 25` | Direction of the next forecast slot, with all upcoming slots as attributes |
| `sensor.fra_betriebsrichtung_next_aircraft_noise` | Next aircraft noise | timestamp | Start of the next forecast slot matching your noise direction |
| `binary_sensor.fra_betriebsrichtung_aircraft_noise` | Aircraft noise | `on` / `off` | Current direction matches your configured noise direction |
| `binary_sensor.fra_betriebsrichtung_aircraft_noise_warning` | Aircraft noise warning | `on` / `off` | Aircraft noise is forecast within your warning window |

### Entity attributes

| Entity | Attributes |
| --- | --- |
| `sensor.fra_betriebsrichtung_current_direction` | `label`, `current_since_start`, `current_duration_minutes`, `source`, `last_update` |
| `sensor.fra_betriebsrichtung_forecast` | `next_slot`, `slots`, `source`, `last_update` |
| `sensor.fra_betriebsrichtung_next_aircraft_noise` | `noise_direction`, `direction`, `from`, `to`, `date`, `end`, `source`, `last_update` |
| `binary_sensor.fra_betriebsrichtung_aircraft_noise` | `noise_direction`, `current_direction`, `source`, `last_update` |
| `binary_sensor.fra_betriebsrichtung_aircraft_noise_warning` | `warning_minutes`, `starts_in_minutes`, `noise_direction`, `next_slot`, `source`, `last_update` |

The `slots` attribute on the forecast sensor contains all upcoming forecast
periods:

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

## Installation

### HACS

1. Open HACS.
2. Add this repository as a custom repository:
   `https://github.com/Orishas/fra_betriebsrichtung`
3. Select category `Integration`.
4. Install `FRA Betriebsrichtung` and restart Home Assistant.
5. Add the integration from **Settings > Devices & services**.

### Manual

Copy `custom_components/fra_betriebsrichtung` into your Home Assistant
configuration directory, restart Home Assistant, and add the integration from
the UI.

## Configuration

1. Go to **Settings > Devices & services > Add integration** and pick
   `FRA Betriebsrichtung`.
2. Choose the operating direction that usually causes aircraft noise at your
   location (`BR 07` for easterly operations or `BR 25` for westerly
   operations).
3. Choose the warning time in minutes for forecast aircraft noise.

You can change both options later from the integration options. Only one
config entry is supported.

## Events

The integration fires `fra_betriebsrichtung_direction_changed` when the
current operating direction changes. Event data:

- `old_direction`
- `new_direction`
- `noise_direction`
- `noise_active`
- `source`
- `last_update`
- `next_slot`

The event is not fired during initial setup.

## Service action

### `fra_betriebsrichtung.refresh`

Refreshes the integration immediately. When called with `response_variable`,
it returns a compact summary for automations:

- `current_direction`
- `forecast_direction`
- `noise_active`
- `next_noise_slot`
- `source`
- `last_update`

If no config entry is loaded or the refresh fails, the action raises a Home
Assistant error so automations do not continue with stale data.

## Automation examples

### Notify when aircraft noise starts

```yaml
automation:
  - alias: "FRA aircraft noise active"
    trigger:
      - platform: state
        entity_id: binary_sensor.fra_betriebsrichtung_aircraft_noise
        to: "on"
    action:
      - service: notify.mobile_app_phone
        data:
          message: "FRA operating direction now matches your local noise direction."
```

### Notify before forecast aircraft noise starts

```yaml
automation:
  - alias: "FRA aircraft noise warning"
    trigger:
      - platform: state
        entity_id: binary_sensor.fra_betriebsrichtung_aircraft_noise_warning
        to: "on"
    action:
      - service: notify.mobile_app_phone
        data:
          message: >-
            FRA aircraft noise is forecast in
            {{ state_attr('binary_sensor.fra_betriebsrichtung_aircraft_noise_warning', 'starts_in_minutes') }}
            minutes.
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

### Refresh before a critical automation

```yaml
automation:
  - alias: "FRA refresh before checking noise"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: fra_betriebsrichtung.refresh
        response_variable: fra
      - condition: template
        value_template: "{{ fra.noise_active }}"
      - service: notify.mobile_app_phone
        data:
          message: "FRA operating direction currently causes local aircraft noise."
```

## Dashboard card

The integration ships its own card. It is served and registered automatically,
so there is no Lovelace resource to add by hand — after installing or updating
the integration, `FRA Betriebsrichtung` appears in the card picker. Force-reload
the browser once (Ctrl/Cmd + Shift + R) if it does not show up right away.

The card needs no configuration at all:

```yaml
type: custom:fra-betriebsrichtung-card
```

It finds the integration entities on its own, reads your configured noise
direction from the integration, and shows:

- the current operating direction with its plain-language label and how long it
  has been running
- when aircraft noise is next expected — or, while it is running, when quiet is
  expected to return
- a forecast timeline where segment width follows real slot duration, missing
  forecast slots stay visible as gaps, and a marker shows the current time

### Layouts

`days` (default) draws one row per day on a 24-hour scale, which makes "quiet on
Sunday morning" readable at a glance:

```yaml
type: custom:fra-betriebsrichtung-card
layout: days
days: 5
```

`compact` draws a single continuous bar, for a dense dashboard:

```yaml
type: custom:fra-betriebsrichtung-card
layout: compact
days: 3
show_hero: false
```

### Card options

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `layout` | `days` \| `compact` | `days` | One row per day, or a single bar |
| `days` | number (1-10) | `5` | Days of forecast to show |
| `title` | string | integration name | Card title |
| `icon` | string | `mdi:airplane-takeoff` | Header icon |
| `show_header` | boolean | `true` | Title row |
| `show_hero` | boolean | `true` | Current state and next change |
| `show_legend` | boolean | `true` | Colour legend |
| `show_now` | boolean | `true` | Current-time marker |
| `show_footer` | boolean | `true` | Source and update time |
| `include_current` | boolean | `true` | Extend the timeline back to when the current direction started |
| `noise_direction` | `auto` \| `BR 07` \| `BR 25` | `auto` | Override the integration's noise direction |
| `forecast_entity` | entity id | auto | Forecast sensor |
| `direction_entity` | entity id | auto | Current direction sensor |
| `noise_entity` | entity id | auto | Aircraft noise binary sensor |

All options are editable in the visual card editor.

### Theming

The card follows your Home Assistant theme. To override its colours, set these
variables in your theme:

```yaml
my_theme:
  fra-noise-color: "#c62828"
  fra-quiet-color: "#2e7d32"
  fra-mixed-color: "#ef6c00"
```

### Entities card

If you prefer a plain list:

```yaml
type: entities
title: FRA Betriebsrichtung
entities:
  - entity: sensor.fra_betriebsrichtung_current_direction
  - entity: sensor.fra_betriebsrichtung_forecast
  - entity: sensor.fra_betriebsrichtung_next_aircraft_noise
  - entity: binary_sensor.fra_betriebsrichtung_aircraft_noise
  - entity: binary_sensor.fra_betriebsrichtung_aircraft_noise_warning
```

## Data sources

The integration polls every 30 minutes and uses public HTML pages only. No
hidden or undocumented API endpoints.

- Primary: <https://www.umwelthaus.org/fluglaerm/anwendungen-service/aktuelle-betriebsrichtung-und-prognose/>
- Fallback: <https://betriebsrichtungsprognose.de/frankfurt-fra/>

The fallback source is used when primary data is incomplete or unavailable.

## Troubleshooting

- If entities are unavailable, open the integration diagnostics from
  **Settings > Devices & services**. `fallback_used: true` means the primary
  source was incomplete and the fallback supplied missing data.
- Website structures can change. Parser failures are handled gracefully — the
  integration does not invent operating direction data.
- If the dashboard card is missing after an update, force-reload the browser.
  The card is versioned with the integration, so a cached copy is replaced on
  the next reload.

## Development

```bash
python -m pytest tests        # integration tests
node --test tests/card.test.mjs   # dashboard card tests
```

## Acknowledgements

Thanks to the Umwelt- und Nachbarschaftshaus / Umwelthaus and to
betriebsrichtungsprognose.de for publishing operating direction information
for Frankfurt Airport.

This integration is not affiliated with, endorsed by, or officially connected
to those websites or their operators.
