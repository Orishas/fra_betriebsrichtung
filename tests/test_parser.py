"""Parser tests for FRA Betriebsrichtung."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
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


FIXTURES = Path(__file__).parent / "fixtures"


def _chart_html(
    labels: list[str],
    direction: list[float],
    wind: list[float] | None = None,
    positive: str = "Ostbetrieb",
    negative: str = "Westbetrieb",
) -> str:
    """Build a page carrying one betriebsrichtungsprognose.de chart config."""
    chart = {
        "id": "chartWestOst",
        "labels": labels,
        "direction": direction,
        "wind": wind if wind is not None else [10] * len(labels),
        "positiveLabel": positive,
        "negativeLabel": negative,
    }
    return f"<script>window.BRP_CHARTS.push({json.dumps(chart)});</script>"


def _fallback_html() -> str:
    return _chart_html(
        ["Tue 21.04 23:00", "Wed 22.04 02:00", "Wed 22.04 05:00"],
        [100, -100, 100],
    )


def test_parse_umwelthaus_current_and_forecast(monkeypatch) -> None:
    """Umwelthaus parser extracts current data and dated forecast slots."""
    _patch_now(monkeypatch, datetime(2026, 4, 22, 12, 0, tzinfo=BERLIN))

    data = parse_umwelthaus(_umwelthaus_html())

    assert data is not None
    assert data.source == SOURCE_UMWELTHAUS
    assert data.current_direction == DIRECTION_BR25
    assert data.current_label == DIRECTION_BR25
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
        # Opposite directions so the two points stay separate slots.
        _chart_html(["Wed 31.12 23:00", "Thu 01.01 02:00"], [100, -100])
    )

    assert data is not None
    assert data.forecast_slots[0].date == "2025-12-31"
    assert data.forecast_slots[0].start_iso == "2025-12-31T23:00:00+01:00"
    assert data.forecast_slots[0].end_iso == "2026-01-01T02:00:00+01:00"


def test_fallback_merges_consecutive_equal_slots(monkeypatch) -> None:
    """Neighbouring points of the same direction become one slot."""
    _patch_now(monkeypatch, datetime(2026, 4, 22, 12, 0, tzinfo=BERLIN))

    data = parse_fallback(
        _chart_html(
            ["Wed 22.04 14:00", "Wed 22.04 17:00", "Wed 22.04 20:00"],
            [-100, -95, -90],
        )
    )

    assert data is not None
    assert len(data.forecast_slots) == 1
    assert data.forecast_slots[0].start_iso == "2026-04-22T14:00:00+02:00"
    assert data.forecast_slots[0].end_iso == "2026-04-22T23:00:00+02:00"


def test_fallback_skips_low_confidence(monkeypatch) -> None:
    """A tendency close to zero leaves a gap instead of a guessed direction."""
    _patch_now(monkeypatch, datetime(2026, 4, 22, 12, 0, tzinfo=BERLIN))

    data = parse_fallback(
        _chart_html(
            ["Wed 22.04 14:00", "Wed 22.04 17:00", "Wed 22.04 20:00"],
            [-100, 5, -100],
        )
    )

    assert data is not None
    assert len(data.forecast_slots) == 2
    assert data.forecast_slots[0].end_iso == "2026-04-22T17:00:00+02:00"
    assert data.forecast_slots[1].start_iso == "2026-04-22T20:00:00+02:00"


def test_fallback_skips_calm_wind(monkeypatch) -> None:
    """A confident tendency at near-zero wind is still dropped."""
    _patch_now(monkeypatch, datetime(2026, 4, 22, 12, 0, tzinfo=BERLIN))

    data = parse_fallback(
        _chart_html(
            ["Wed 22.04 14:00", "Wed 22.04 17:00", "Wed 22.04 20:00"],
            [-100, 95, -100],
            wind=[10, 1.1, 10],
        )
    )

    assert data is not None
    assert all(slot.direction == DIRECTION_BR25 for slot in data.forecast_slots)
    assert len(data.forecast_slots) == 2


def test_fallback_ignores_north_south_axis(monkeypatch) -> None:
    """The runway 18/36 chart does not map onto BR 07 / BR 25."""
    _patch_now(monkeypatch, datetime(2026, 4, 22, 12, 0, tzinfo=BERLIN))

    data = parse_fallback(
        _chart_html(
            ["Wed 22.04 14:00", "Wed 22.04 17:00"],
            [-100, -100],
            positive="Nordbetrieb",
            negative="Südbetrieb",
        )
    )

    assert data is None


def test_parse_fallback_against_captured_page(monkeypatch) -> None:
    """The parser handles a real capture of the source page."""
    _patch_now(monkeypatch, datetime(2026, 8, 20, 12, 30, tzinfo=BERLIN))

    data = parse_fallback((FIXTURES / "brp_frankfurt.html").read_text())

    assert data is not None
    assert data.source == SOURCE_FALLBACK
    assert data.forecast_slots

    # The capture holds five days of data across both runway axes; only the
    # east/west axis is used, and noise around zero must not become a slot.
    assert data.forecast_slots[0].direction == DIRECTION_BR25
    assert data.forecast_slots[0].start_iso == "2026-08-20T12:11:00+02:00"
    assert data.forecast_slots[-1].direction == DIRECTION_BR07

    # The official forecast for the same window changes direction once, late
    # on 23.08. Anything close to that is fine; a dozen flips is not.
    changes = sum(
        1
        for previous, current in zip(data.forecast_slots, data.forecast_slots[1:])
        if previous.direction != current.direction
    )
    assert changes == 1


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
