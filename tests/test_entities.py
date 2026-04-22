"""Entity and diagnostics tests for FRA Betriebsrichtung."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from custom_components.fra_betriebsrichtung.binary_sensor import (
    FraBetriebsrichtungForecastNoiseSensor,
)
from custom_components.fra_betriebsrichtung.const import (
    CONF_NOISE_DIRECTION,
    DIRECTION_BR07,
    DIRECTION_BR25,
    EVENT_DIRECTION_CHANGED,
)
from custom_components.fra_betriebsrichtung.coordinator import (
    FraBetriebsrichtungCoordinator,
)
from custom_components.fra_betriebsrichtung.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.fra_betriebsrichtung.entity import (
    next_noise_slot,
    slot_matches_direction,
)
from custom_components.fra_betriebsrichtung.models import (
    ForecastSlot,
    FraBetriebsrichtungData,
    SourceHealth,
)
from custom_components.fra_betriebsrichtung.sensor import FraNextNoiseSensor


def _slots() -> tuple[ForecastSlot, ...]:
    return (
        ForecastSlot(
            start="06:00",
            end="14:00",
            direction=DIRECTION_BR07,
            date="2026-04-22",
            start_iso="2026-04-22T06:00:00+02:00",
            end_iso="2026-04-22T14:00:00+02:00",
        ),
        ForecastSlot(
            start="14:00",
            end="22:00",
            direction=DIRECTION_BR25,
            date="2026-04-22",
            start_iso="2026-04-22T14:00:00+02:00",
            end_iso="2026-04-22T22:00:00+02:00",
        ),
    )


def _data() -> FraBetriebsrichtungData:
    return FraBetriebsrichtungData(
        current_direction=DIRECTION_BR25,
        current_since="22. Apr., 06.00 Uhr",
        forecast_summary="BR 07 ab 06:00",
        forecast_slots=_slots(),
        source="test",
        last_update="2026-04-22T06:05:00+02:00",
        health=SourceHealth(
            primary_ok=True,
            fallback_ok=None,
            fallback_used=False,
            last_success="2026-04-22T06:05:00+02:00",
            errors=(),
        ),
    )


def _entry(data: FraBetriebsrichtungData, noise_direction: str):
    return SimpleNamespace(
        options={CONF_NOISE_DIRECTION: noise_direction},
        runtime_data=SimpleNamespace(coordinator=SimpleNamespace(data=data)),
    )


def test_forecast_noise_binary_sensor_uses_next_slot() -> None:
    """Forecast noise sensor is on when the next slot matches the noise direction."""
    data = _data()
    entry = _entry(data, DIRECTION_BR07)
    sensor = FraBetriebsrichtungForecastNoiseSensor(
        entry,
        entry.runtime_data.coordinator,
    )

    assert sensor.available is True
    assert sensor.is_on is True
    assert sensor.extra_state_attributes["forecast_direction"] == DIRECTION_BR07


def test_next_noise_sensor_finds_first_matching_slot() -> None:
    """Next noise sensor returns the first forecast slot matching local noise."""
    data = _data()
    entry = _entry(data, DIRECTION_BR25)
    sensor = FraNextNoiseSensor(entry, entry.runtime_data.coordinator)

    assert next_noise_slot(data, DIRECTION_BR25) == data.forecast_slots[1]
    assert sensor.native_value.isoformat() == "2026-04-22T14:00:00+02:00"
    assert sensor.extra_state_attributes["direction"] == DIRECTION_BR25
    assert sensor.extra_state_attributes["date"] == "2026-04-22"


def test_slot_matches_combined_direction() -> None:
    """Slots with combined directions match either included direction."""
    slot = ForecastSlot("22:00", "06:00", "BR 07 / BR 25")

    assert slot_matches_direction(slot, DIRECTION_BR07) is True
    assert slot_matches_direction(slot, DIRECTION_BR25) is True


def test_diagnostics_uses_sanitized_data_only() -> None:
    """Diagnostics expose normalized data but no raw HTML payloads."""
    diagnostics = asyncio.run(
        async_get_config_entry_diagnostics(None, _entry(_data(), DIRECTION_BR25))
    )

    text = repr(diagnostics).lower()
    assert "<html" not in text
    assert "data-graph" not in text
    assert diagnostics["data"]["forecast_slots"][0]["date"] == "2026-04-22"
    assert diagnostics["data"]["errors"] == []


def test_direction_changed_event_fires_once_for_real_change() -> None:
    """Direction change event is skipped on setup and fired once on real changes."""

    class Bus:
        def __init__(self) -> None:
            self.events = []

        def async_fire(self, event_type, event_data) -> None:
            self.events.append((event_type, event_data))

    coordinator = FraBetriebsrichtungCoordinator.__new__(FraBetriebsrichtungCoordinator)
    coordinator.hass = SimpleNamespace(bus=Bus())
    coordinator._entry = SimpleNamespace(options={CONF_NOISE_DIRECTION: DIRECTION_BR25})
    data = _data()

    coordinator._fire_direction_changed(None, data)
    coordinator._fire_direction_changed(DIRECTION_BR07, data)
    coordinator._fire_direction_changed(DIRECTION_BR25, data)

    assert len(coordinator.hass.bus.events) == 1
    event_type, event_data = coordinator.hass.bus.events[0]
    assert event_type == EVENT_DIRECTION_CHANGED
    assert event_data["old_direction"] == DIRECTION_BR07
    assert event_data["new_direction"] == DIRECTION_BR25
    assert event_data["noise_active"] is True
    assert event_data["next_slot"] == data.forecast_slots[0].as_dict()
