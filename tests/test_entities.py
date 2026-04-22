"""Entity and diagnostics tests for FRA Betriebsrichtung."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from custom_components.fra_betriebsrichtung import _async_handle_refresh, async_setup
from custom_components.fra_betriebsrichtung.binary_sensor import (
    FraBetriebsrichtungDirectionChangeForecastSensor,
    FraBetriebsrichtungForecastNoiseSensor,
    FraBetriebsrichtungSoonNoiseSensor,
)
from custom_components.fra_betriebsrichtung.const import (
    CONF_NOISE_DIRECTION,
    CONF_WARNING_MINUTES,
    DIRECTION_BR07,
    DIRECTION_BR25,
    DOMAIN,
    EVENT_DIRECTION_CHANGED,
)
from custom_components.fra_betriebsrichtung.coordinator import (
    FraBetriebsrichtungCoordinator,
)
from custom_components.fra_betriebsrichtung.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.fra_betriebsrichtung.entity import (
    configured_warning_minutes,
    next_noise_slot,
    slot_matches_direction,
)
from custom_components.fra_betriebsrichtung.models import (
    ForecastSlot,
    FraBetriebsrichtungData,
    SourceHealth,
)
from custom_components.fra_betriebsrichtung.sensor import (
    FraNextDirectionChangeSensor,
    FraNextNoiseSensor,
)

BERLIN = ZoneInfo("Europe/Berlin")


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


def _entry(
    data: FraBetriebsrichtungData,
    noise_direction: str,
    warning_minutes: int = 60,
):
    return SimpleNamespace(
        options={
            CONF_NOISE_DIRECTION: noise_direction,
            CONF_WARNING_MINUTES: warning_minutes,
        },
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


def test_aircraft_noise_soon_sensor_uses_warning_window(monkeypatch) -> None:
    """Aircraft noise soon sensor is on inside the configured warning window."""
    from custom_components.fra_betriebsrichtung import binary_sensor

    monkeypatch.setattr(
        binary_sensor.dt_util,
        "now",
        lambda: __import__("datetime").datetime(
            2026, 4, 22, 5, 15, tzinfo=BERLIN
        ),
    )
    data = _data()
    entry = _entry(data, DIRECTION_BR07, warning_minutes=60)
    sensor = FraBetriebsrichtungSoonNoiseSensor(
        entry,
        entry.runtime_data.coordinator,
    )

    assert configured_warning_minutes(entry) == 60
    assert sensor.available is True
    assert sensor.is_on is True
    assert sensor.extra_state_attributes["starts_in_minutes"] == 45


def test_aircraft_noise_soon_sensor_is_off_when_noise_is_already_active(
    monkeypatch,
) -> None:
    """Aircraft noise soon sensor is off when current noise is already active."""
    from custom_components.fra_betriebsrichtung import binary_sensor

    monkeypatch.setattr(
        binary_sensor.dt_util,
        "now",
        lambda: __import__("datetime").datetime(
            2026, 4, 22, 13, 30, tzinfo=BERLIN
        ),
    )
    data = _data()
    entry = _entry(data, DIRECTION_BR25, warning_minutes=60)
    sensor = FraBetriebsrichtungSoonNoiseSensor(
        entry,
        entry.runtime_data.coordinator,
    )

    assert sensor.is_on is False


def test_direction_change_forecast_sensor_uses_next_slot() -> None:
    """Direction change forecast is on when the next slot differs."""
    data = _data()
    sensor = FraBetriebsrichtungDirectionChangeForecastSensor(
        SimpleNamespace(data=data)
    )

    assert sensor.available is True
    assert sensor.is_on is True
    assert sensor.extra_state_attributes["forecast_direction"] == DIRECTION_BR07


def test_next_direction_change_sensor_finds_first_different_slot() -> None:
    """Next direction change sensor returns the first differing forecast slot."""
    data = _data()
    sensor = FraNextDirectionChangeSensor(SimpleNamespace(data=data))

    assert sensor.native_value.isoformat() == "2026-04-22T06:00:00+02:00"
    assert sensor.extra_state_attributes["new_direction"] == DIRECTION_BR07


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


def test_refresh_service_returns_response_and_refreshes() -> None:
    """Manual refresh action refreshes the coordinator and returns response data."""

    class Coordinator:
        def __init__(self) -> None:
            self.data = _data()
            self.refreshed = False

        async def async_request_refresh(self) -> None:
            self.refreshed = True

    coordinator = Coordinator()
    entry = SimpleNamespace(
        options={CONF_NOISE_DIRECTION: DIRECTION_BR25},
        runtime_data=SimpleNamespace(coordinator=coordinator),
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry": entry}})

    response = asyncio.run(
        _async_handle_refresh(hass, SimpleNamespace(return_response=True))
    )

    assert coordinator.refreshed is True
    assert response["current_direction"] == DIRECTION_BR25
    assert response["forecast_direction"] == DIRECTION_BR07
    assert response["noise_active"] is True
    assert response["forecast_noise_active"] is False
    assert response["next_direction_change"] == _slots()[0].as_dict()


def test_refresh_service_is_registered_in_async_setup() -> None:
    """Manual refresh action is registered during integration setup."""

    class Services:
        def __init__(self) -> None:
            self.calls = []

        def async_register(self, *args, **kwargs) -> None:
            self.calls.append((args, kwargs))

    services = Services()
    hass = SimpleNamespace(data={}, services=services)

    assert asyncio.run(async_setup(hass, {})) is True
    args, kwargs = services.calls[0]
    assert args[:2] == (DOMAIN, "refresh")
    assert kwargs["supports_response"] == "optional"


def test_refresh_service_without_loaded_entry_is_tolerant() -> None:
    """Manual refresh action returns a response instead of failing without entry."""
    hass = SimpleNamespace(data={DOMAIN: {}})

    response = asyncio.run(
        _async_handle_refresh(hass, SimpleNamespace(return_response=True))
    )

    assert response["current_direction"] is None
    assert response["error"] == "no_loaded_config_entry"
