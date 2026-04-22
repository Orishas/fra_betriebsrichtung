"""Parser tests for FRA Betriebsrichtung."""

from __future__ import annotations

from datetime import datetime
import json
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from custom_components.fra_betriebsrichtung.const import (
    DIRECTION_BR07,
    DIRECTION_BR25,
    SOURCE_FALLBACK,
    SOURCE_UMWELTHAUS,
)
from custom_components.fra_betriebsrichtung.models import (
    ForecastSlot,
    FraBetriebsrichtungData,
)
from custom_components.fra_betriebsrichtung import parser
from custom_components.fra_betriebsrichtung.parser import (
    merge_data,
    parse_fallback,
    parse_umwelthaus,
)

BERLIN = ZoneInfo("Europe/Berlin")


class FixedDateTime(datetime):
    """Datetime with a fixed now for parser tests."""

    fixed_now = datetime(2026, 4, 22, 12, 0, tzinfo=BERLIN)

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        """Return a fixed datetime."""
        if tz is None:
            return cls.fixed_now.replace(tzinfo=None)
        return cls.fixed_now.astimezone(tz)


def _patch_now(monkeypatch, value: datetime) -> None:
    FixedDateTime.fixed_now = value
    monkeypatch.setattr(parser, "datetime", FixedDateTime)


def _timestamp(value: datetime) -> int:
    return int(value.timestamp())


def _umwelthaus_html() -> str:
    graph = {
        "periods": [
            {
                "date": _timestamp(datetime(2026, 4, 22, 6, 0, tzinfo=BERLIN)),
                "state": 1,
            },
            {
                "date": _timestamp(datetime(2026, 4, 22, 14, 0, tzinfo=BERLIN)),
                "state": 3,
            },
            {
                "date": _timestamp(datetime(2026, 4, 22, 22, 0, tzinfo=BERLIN)),
                "state": 3,
            },
        ]
    }
    return f"""
    <html>
      <figure class="br-display-br">
        <h4>BR 25</h4>
        <figcaption><p>Die aktuelle Betriebsrichtung gilt seit 22. Apr., 06.00 Uhr</p></figcaption>
      </figure>
      <div id="brp">
        <p class="introtext">Aktuell (22.04.2026 08:30): Prognose fuer Frankfurt.</p>
      </div>
      <div class="brp-graph" data-graph="{quote_plus(json.dumps(graph))}"></div>
    </html>
    """


def _fallback_html() -> str:
    return """
    <script>
      labels: ["Tue 21.04 23:00", "Wed 22.04 02:00", "Wed 22.04 05:00"]
      var abflugData = [1, -1, 1]
    </script>
    """


def test_parse_umwelthaus_current_and_forecast(monkeypatch) -> None:
    """Umwelthaus parser extracts current data and dated forecast slots."""
    _patch_now(monkeypatch, datetime(2026, 4, 22, 12, 0, tzinfo=BERLIN))

    data = parse_umwelthaus(_umwelthaus_html())

    assert data is not None
    assert data.source == SOURCE_UMWELTHAUS
    assert data.current_direction == DIRECTION_BR25
    assert data.current_label == DIRECTION_BR25
    assert data.current_since == "22. Apr., 06.00 Uhr"
    assert data.current_since_start == "2026-04-22T06:00:00+02:00"
    assert data.current_duration_minutes == 360
    assert data.last_update == "22.04.2026 08:30"
    assert data.forecast_slots[0].as_dict() == {
        "from": "06:00",
        "to": "14:00",
        "direction": DIRECTION_BR25,
        "date": "2026-04-22",
        "start": "2026-04-22T06:00:00+02:00",
        "end": "2026-04-22T14:00:00+02:00",
    }


def test_parse_fallback_dated_slots(monkeypatch) -> None:
    """Fallback parser extracts dated forecast slots."""
    _patch_now(monkeypatch, datetime(2026, 4, 22, 12, 0, tzinfo=BERLIN))

    data = parse_fallback(_fallback_html())

    assert data is not None
    assert data.source == SOURCE_FALLBACK
    assert data.forecast_summary == "BR 07 ab 23:00"
    assert data.forecast_slots[0].as_dict() == {
        "from": "23:00",
        "to": "02:00",
        "direction": DIRECTION_BR07,
        "date": "2026-04-21",
        "start": "2026-04-21T23:00:00+02:00",
        "end": "2026-04-22T02:00:00+02:00",
    }
    assert data.forecast_slots[1].direction == DIRECTION_BR25


def test_fallback_year_rollover(monkeypatch) -> None:
    """Fallback labels around New Year are assigned to the closest year."""
    _patch_now(monkeypatch, datetime(2026, 1, 1, 12, 0, tzinfo=BERLIN))

    data = parse_fallback(
        """
        <script>
          labels: ["Wed 31.12 23:00", "Thu 01.01 02:00"]
          var abflugData = [1, 1]
        </script>
        """
    )

    assert data is not None
    assert data.forecast_slots[0].date == "2025-12-31"
    assert data.forecast_slots[0].start_iso == "2025-12-31T23:00:00+01:00"
    assert data.forecast_slots[0].end_iso == "2026-01-01T02:00:00+01:00"


def test_merge_data_uses_fallback_only_for_missing_primary_parts() -> None:
    """Merge keeps primary current data and fills missing forecast from fallback."""
    primary = FraBetriebsrichtungData(
        current_direction=DIRECTION_BR25,
        current_label=DIRECTION_BR25,
        source=SOURCE_UMWELTHAUS,
    )
    fallback = FraBetriebsrichtungData(
        forecast_summary="BR 07 ab 23:00",
        forecast_slots=(
            ForecastSlot(
                start="23:00",
                end="02:00",
                direction=DIRECTION_BR07,
                date="2026-04-21",
                start_iso="2026-04-21T23:00:00+02:00",
                end_iso="2026-04-22T02:00:00+02:00",
            ),
        ),
        source=SOURCE_FALLBACK,
    )

    data = merge_data(primary, fallback)

    assert data is not None
    assert data.current_direction == DIRECTION_BR25
    assert data.forecast_slots[0].direction == DIRECTION_BR07
    assert data.fallback_used is True
    assert data.source == f"{SOURCE_UMWELTHAUS}; {SOURCE_FALLBACK}"
