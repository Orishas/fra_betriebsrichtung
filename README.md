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

Existing installations that already registered `fra_fra_betriebsrichtung_*`
entity IDs keep those registry IDs until they are manually renamed in Home
Assistant or the integration is removed and added again.

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

## Dashboard example

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

### Forecast bar with button-card

For a compact horizontal forecast bar, install
[`button-card`](https://github.com/custom-cards/button-card) and adjust
`noise_direction` to the direction that causes aircraft noise at your
location. The bar colors the configured noise direction red, the other
direction green, and direction changes orange.

```yaml
type: vertical-stack
cards:
  - type: heading
    icon: mdi:airplane-marker
    heading: FRA Betriebsrichtung
    badges:
      - type: entity
        entity: sensor.fra_betriebsrichtung_current_direction
        name: Current
        show_state: true
        show_icon: true
        state_content:
          - label
        tap_action:
          action: more-info
      - type: entity
        entity: binary_sensor.fra_betriebsrichtung_aircraft_noise
        name: Noise
        show_state: true
        show_icon: true
        state_content:
          - state
        tap_action:
          action: more-info
      - type: entity
        entity: sensor.fra_betriebsrichtung_next_aircraft_noise
        name: Next noise
        show_state: true
        show_icon: true
        state_content:
          - state
        tap_action:
          action: more-info
  - type: custom:button-card
    entity: sensor.fra_betriebsrichtung_forecast
    variables:
      noise_direction: BR 07
    show_name: false
    show_icon: false
    show_state: false
    tap_action:
      action: more-info
    custom_fields:
      bar: |
        [[[
          const slots = entity.attributes.slots || [];
          const noiseDirection = variables.noise_direction || "BR 07";

          if (!slots.length) {
            return `<div class="empty">No forecast available</div>`;
          }

          const escapeHtml = (value) => String(value ?? "").replace(
            /[&<>"']/g,
            (char) => ({
              "&": "&amp;",
              "<": "&lt;",
              ">": "&gt;",
              '"': "&quot;",
              "'": "&#39;",
            }[char]),
          );
          const directionParts = (direction) => String(direction || "")
            .split("/")
            .map((part) => part.trim());
          const isNoiseDirection = (direction) =>
            directionParts(direction).includes(noiseDirection);
          const color = (direction) =>
            isNoiseDirection(direction)
              ? "var(--error-color)"
              : "var(--success-color)";
          const transitionColor = "var(--warning-color)";
          const isTransition = (index) =>
            index > 0 && slots[index - 1].direction !== slots[index].direction;
          const background = (slot, index) => {
            if (!isTransition(index)) {
              return color(slot.direction);
            }

            const previousColor = color(slots[index - 1].direction);
            const currentColor = color(slot.direction);
            return `linear-gradient(90deg,
              ${previousColor} 0%,
              ${previousColor} 40%,
              ${transitionColor} 40%,
              ${transitionColor} 60%,
              ${currentColor} 60%,
              ${currentColor} 100%)`;
          };
          const title = (slot, index) => {
            const status = isNoiseDirection(slot.direction)
              ? "noise direction"
              : "other direction";

            if (isTransition(index)) {
              return `${slot.date} ${slot.from}-${slot.to} - change from ${slots[index - 1].direction} to ${slot.direction}`;
            }

            return `${slot.date} ${slot.from}-${slot.to} - ${slot.direction} - ${status}`;
          };

          const firstStart = new Date(slots[0].start).getTime();
          const lastEnd = new Date(slots[slots.length - 1].end).getTime();
          const now = Date.now();
          const nowPercent = now >= firstStart && now <= lastEnd
            ? ((now - firstStart) / (lastEnd - firstStart)) * 100
            : null;

          return `
            <div class="wrap">
              <div class="bar" style="grid-template-columns: repeat(${slots.length}, 1fr);">
                ${slots.map((slot, index) => `
                  <div class="segment ${isTransition(index) ? "transition" : ""}"
                       style="background: ${background(slot, index)}"
                       title="${escapeHtml(title(slot, index))}">
                  </div>
                `).join("")}
                ${nowPercent !== null ? `
                  <div class="now-marker" style="left: ${nowPercent}%"></div>
                ` : ""}
              </div>
              <div class="labels" style="grid-template-columns: repeat(${slots.length}, 1fr);">
                ${slots.map((slot, index) => `
                  <div class="label">
                    ${index % 3 === 0
                      ? new Date(slot.start).toLocaleDateString(undefined, {
                          weekday: "short",
                          day: "2-digit",
                          month: "2-digit",
                        })
                      : ""}
                  </div>
                `).join("")}
              </div>
              <div class="legend">
                <span><i class="noise"></i>${escapeHtml(noiseDirection)} noise</span>
                <span><i class="other"></i>Other direction</span>
                <span><i class="transition-key"></i>Change</span>
              </div>
            </div>
          `;
        ]]]
    styles:
      card:
        - padding: 8px
      custom_fields:
        bar:
          - width: 100%
    extra_styles: |
      .wrap {
        width: 100%;
      }

      .bar {
        position: relative;
        display: grid;
        height: 16px;
        border-radius: 5px;
        overflow: hidden;
        background: var(--divider-color);
      }

      .segment {
        border-right: 1px solid rgba(255, 255, 255, 0.45);
      }

      .segment:last-child {
        border-right: none;
      }

      .transition {
        box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.85);
      }

      .now-marker {
        position: absolute;
        top: -2px;
        bottom: -2px;
        width: 2px;
        background: var(--primary-text-color);
        box-shadow: 0 0 3px rgba(0, 0, 0, 0.45);
        z-index: 3;
      }

      .labels {
        display: grid;
        margin-top: 3px;
      }

      .label {
        font-size: 8px;
        line-height: 9px;
        color: var(--secondary-text-color);
        text-align: left;
        white-space: nowrap;
      }

      .legend {
        display: flex;
        gap: 10px;
        margin-top: 5px;
        font-size: 9px;
        line-height: 10px;
        color: var(--secondary-text-color);
        align-items: center;
        flex-wrap: wrap;
      }

      .legend span {
        display: inline-flex;
        align-items: center;
        gap: 3px;
      }

      .legend i {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 2px;
      }

      .legend .noise {
        background: var(--error-color);
      }

      .legend .other {
        background: var(--success-color);
      }

      .legend .transition-key {
        background: var(--warning-color);
      }

      .empty {
        font-size: 11px;
        color: var(--secondary-text-color);
      }
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

## Acknowledgements

Thanks to the Umwelt- und Nachbarschaftshaus / Umwelthaus and to
betriebsrichtungsprognose.de for publishing operating direction information
for Frankfurt Airport.

Thanks to [@thecem](https://github.com/thecem) for contributing the forecast
dashboard card idea and example.

This integration is not affiliated with, endorsed by, or officially connected
to those websites or their operators.
