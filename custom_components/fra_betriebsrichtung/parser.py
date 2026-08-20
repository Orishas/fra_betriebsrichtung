"""HTML parsers for FRA operating direction data."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import json
import re
from typing import Any
from urllib.parse import unquote_plus
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .const import (
    DIRECTION_BR07,
    DIRECTION_BR25,
    SOURCE_FALLBACK,
    SOURCE_UMWELTHAUS,
)
from .models import ForecastSlot, FraBetriebsrichtungData, SourceHealth

AIRPORT_TZ = ZoneInfo("Europe/Berlin")

_BR07_RE = re.compile(r"\b(?:BR|Betriebsrichtung)\s*0?7\b|\b07\s*\(Ost\)", re.I)
_BR25_RE = re.compile(r"\b(?:BR|Betriebsrichtung)\s*25\b|\b25\s*\(West\)", re.I)

# betriebsrichtungsprognose.de ships one chart config per runway axis.
_BRP_CHART_RE = re.compile(r"window\.BRP_CHARTS\.push\(\s*(\{.*?\})\s*\)\s*;", re.S)

# Only the east/west axis maps onto Frankfurt operating directions. The
# north/south chart describes runway 18/36 and is skipped.
_BRP_AXIS_LABELS = {
    "ostbetrieb": DIRECTION_BR07,
    "westbetrieb": DIRECTION_BR25,
}

# The source encodes a tendency from -100 to 100 derived from wind data.
# Near zero it flips sign on noise alone, so weak readings are dropped
# instead of being reported as a hard direction.
BRP_MIN_CONFIDENCE = 40

# Below this wind speed the tendency is not meaningful either: with almost
# no wind an airport follows its preferred operating direction rather than
# the wind, which this source does not model. Observed on 2026-08-20, where
# it reported a three-hour swing to BR 07 at 1.1 kn while the official
# forecast stayed on BR 25 throughout.
BRP_MIN_WIND_KN = 3

BRP_SLOT_HOURS = 3


def parse_umwelthaus(html: str) -> FraBetriebsrichtungData | None:
    """Parse the Umwelthaus operating direction page."""
    soup = BeautifulSoup(html, "html.parser")

    current_label = _clean_text(_select_text(soup, "figure.br-display-br h4"))
    current_direction = normalize_direction(current_label)
    current_since = _parse_current_since(soup)
    current_since_start, current_duration_minutes = _parse_current_since_start(
        current_since
    )

    forecast_summary = _clean_text(_select_text(soup, "#brp p.introtext"))
    last_update = _parse_last_update(forecast_summary)
    forecast_slots = _parse_umwelthaus_slots(soup)

    data = FraBetriebsrichtungData(
        current_direction=current_direction,
        current_label=current_label,
        current_since_start=current_since_start,
        current_duration_minutes=current_duration_minutes,
        forecast_summary=forecast_summary,
        forecast_slots=forecast_slots,
        source=SOURCE_UMWELTHAUS,
        last_update=last_update,
    )
    return data if data.has_any_data else None


def parse_fallback(html: str) -> FraBetriebsrichtungData | None:
    """Parse the betriebsrichtungsprognose.de fallback page."""
    chart = _brp_chart(html)
    if chart is None:
        return None

    slots = _brp_slots(chart)
    if not slots:
        return None

    first = slots[0]
    data = FraBetriebsrichtungData(
        forecast_summary=f"{first.direction} ab {first.start}",
        forecast_slots=slots,
        source=SOURCE_FALLBACK,
    )
    return data if data.has_any_data else None


def _brp_chart(html: str) -> dict[str, Any] | None:
    """Return the chart config whose axis maps onto BR 07 / BR 25."""
    for match in _BRP_CHART_RE.finditer(html):
        try:
            chart = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(chart, dict):
            continue
        if _brp_axis(chart) is not None:
            return chart
    return None


def _brp_axis(chart: dict[str, Any]) -> tuple[str, str] | None:
    """Return (positive, negative) directions for a chart, if it maps."""
    positive = _BRP_AXIS_LABELS.get(str(chart.get("positiveLabel", "")).strip().lower())
    negative = _BRP_AXIS_LABELS.get(str(chart.get("negativeLabel", "")).strip().lower())
    if positive is None or negative is None:
        return None
    return positive, negative


def _brp_slots(chart: dict[str, Any]) -> tuple[ForecastSlot, ...]:
    """Build merged forecast slots from a chart config."""
    axis = _brp_axis(chart)
    labels = chart.get("labels")
    values = chart.get("direction")
    if axis is None or not isinstance(labels, list) or not isinstance(values, list):
        return ()

    winds = chart.get("wind")
    if not isinstance(winds, list):
        winds = []

    positive, negative = axis
    slots: list[ForecastSlot] = []
    count = min(len(labels), len(values))
    for index in range(count):
        start = _datetime_from_fallback_label(labels[index])
        if start is None:
            continue
        end = (
            _datetime_from_fallback_label(labels[index + 1])
            if index + 1 < count
            else start + timedelta(hours=BRP_SLOT_HOURS)
        )
        if end is None or end <= start:
            continue

        wind = winds[index] if index < len(winds) else None
        direction = _brp_direction(values[index], wind, positive, negative)
        if direction is None:
            # Not meaningful — leave a gap rather than reporting a
            # direction the source cannot support.
            continue

        previous = slots[-1] if slots else None
        if (
            previous is not None
            and previous.direction == direction
            and previous.end_iso == start.isoformat()
        ):
            slots[-1] = replace(
                previous,
                end=end.strftime("%H:%M"),
                end_iso=end.isoformat(),
            )
            continue

        slots.append(
            ForecastSlot(
                start=start.strftime("%H:%M"),
                end=end.strftime("%H:%M"),
                direction=direction,
                date=start.date().isoformat(),
                start_iso=start.isoformat(),
                end_iso=end.isoformat(),
            )
        )
    return tuple(slots)


def _brp_direction(
    value: Any,
    wind: Any,
    positive: str,
    negative: str,
) -> str | None:
    """Map a tendency value onto a direction, or None when it is too weak."""
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    if abs(numeric_value) < BRP_MIN_CONFIDENCE:
        return None
    if wind is not None:
        try:
            if float(wind) < BRP_MIN_WIND_KN:
                return None
        except (TypeError, ValueError):
            pass
    return positive if numeric_value > 0 else negative


def merge_data(
    primary: FraBetriebsrichtungData | None, fallback: FraBetriebsrichtungData | None
) -> FraBetriebsrichtungData | None:
    """Merge primary and fallback data without inventing missing values."""
    if primary is None:
        return fallback
    if fallback is None:
        return primary

    uses_fallback = (
        not primary.current_direction
        and fallback.current_direction
        or not primary.has_forecast
        and fallback.has_forecast
    )
    source = primary.source
    if uses_fallback and fallback.source:
        source = (
            f"{primary.source}; {fallback.source}" if primary.source else fallback.source
        )

    return FraBetriebsrichtungData(
        current_direction=primary.current_direction or fallback.current_direction,
        current_label=primary.current_label or fallback.current_label,
        current_since_start=primary.current_since_start or fallback.current_since_start,
        current_duration_minutes=primary.current_duration_minutes
        if primary.current_duration_minutes is not None
        else fallback.current_duration_minutes,
        forecast_summary=primary.forecast_summary or fallback.forecast_summary,
        forecast_slots=primary.forecast_slots or fallback.forecast_slots,
        source=source,
        last_update=primary.last_update or fallback.last_update,
        health=SourceHealth(fallback_used=uses_fallback),
    )


def normalize_direction(text: str | None) -> str | None:
    """Normalize a text fragment to BR 07 or BR 25."""
    if not text:
        return None
    if _BR07_RE.search(text):
        return DIRECTION_BR07
    if _BR25_RE.search(text):
        return DIRECTION_BR25
    return None


def _parse_current_since(soup: BeautifulSoup) -> str | None:
    current_figure = soup.select_one("figure.br-display-br")
    if current_figure is None:
        return None

    text = _clean_text(_select_text(current_figure, "figcaption p"))
    if not text:
        return None

    match = re.search(r"\bseit\s+(.+)$", text, flags=re.I)
    return match.group(1).strip() if match else None


def _parse_last_update(summary: str | None) -> str | None:
    if not summary:
        return None
    match = re.search(r"Aktuell\s*\(([^)]+)\)", summary)
    return match.group(1).strip() if match else None


def _parse_current_since_start(value: str | None) -> tuple[str | None, int | None]:
    if not value:
        return None, None

    month_names = {
        "jan": 1,
        "januar": 1,
        "feb": 2,
        "februar": 2,
        "mär": 3,
        "märz": 3,
        "maer": 3,
        "maerz": 3,
        "mar": 3,
        "mrz": 3,
        "apr": 4,
        "april": 4,
        "mai": 5,
        "jun": 6,
        "juni": 6,
        "jul": 7,
        "juli": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "sept": 9,
        "september": 9,
        "okt": 10,
        "oktober": 10,
        "nov": 11,
        "november": 11,
        "dez": 12,
        "dezember": 12,
    }
    match = re.search(
        r"\b(\d{1,2})\.\s*([A-Za-zÄÖÜäöü]+)\.?,?\s*(\d{1,2})[.:](\d{2})",
        value,
    )
    if not match:
        return None, None

    day = int(match.group(1))
    month = month_names.get(match.group(2).lower().replace("ä", "ae"))
    hour = int(match.group(3))
    minute = int(match.group(4))
    if month is None:
        return None, None

    now = datetime.now(AIRPORT_TZ)
    try:
        parsed = datetime(now.year, month, day, hour, minute, tzinfo=AIRPORT_TZ)
    except ValueError:
        return None, None

    if parsed > now + timedelta(days=1):
        parsed = parsed.replace(year=parsed.year - 1)
    duration = max(0, round((now - parsed).total_seconds() / 60))
    return parsed.isoformat(), duration


def _parse_umwelthaus_slots(soup: BeautifulSoup) -> tuple[ForecastSlot, ...]:
    graph = soup.select_one(".brp-graph[data-graph]")
    if graph is None:
        return ()

    raw_graph = graph.get("data-graph")
    if not raw_graph:
        return ()

    graph_data = json.loads(unquote_plus(raw_graph))
    periods = graph_data.get("periods")
    if not isinstance(periods, list):
        return ()

    slots: list[ForecastSlot] = []
    for index, period in enumerate(periods):
        if not isinstance(period, dict):
            continue
        start_dt = _period_datetime(period)
        if start_dt is None:
            continue
        end_dt = (
            _period_datetime(periods[index + 1])
            if index + 1 < len(periods) and isinstance(periods[index + 1], dict)
            else start_dt + timedelta(hours=8)
        )
        if end_dt is None:
            continue
        direction = _direction_from_period(period)
        if direction is None:
            continue
        slots.append(
            ForecastSlot(
                start=start_dt.strftime("%H:%M"),
                end=end_dt.strftime("%H:%M"),
                direction=direction,
                date=start_dt.date().isoformat(),
                start_iso=start_dt.isoformat(),
                end_iso=end_dt.isoformat(),
            )
        )
    return tuple(slots)


def _period_datetime(period: dict[str, Any]) -> datetime | None:
    timestamp = period.get("date")
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp, AIRPORT_TZ)
    return None


def _direction_from_period(period: dict[str, Any]) -> str | None:
    directions: list[str] = []
    for key in ("startState", "endState", "state"):
        direction = _direction_from_state(period.get(key))
        if direction and direction not in directions:
            directions.append(direction)

    if not directions:
        return None
    if len(directions) == 1:
        return directions[0]
    return " / ".join(directions)


def _direction_from_state(value: Any) -> str | None:
    state = str(value)
    if state == "3":
        return DIRECTION_BR07
    if state == "1":
        return DIRECTION_BR25
    return None


def _datetime_from_fallback_label(label: Any) -> datetime | None:
    if not isinstance(label, str):
        return None

    match = re.search(r"\b(\d{1,2})\.(\d{1,2})\s+(\d{2}):(\d{2})$", label.strip())
    if not match:
        return None

    now = datetime.now(AIRPORT_TZ)
    day, month, hour, minute = (int(part) for part in match.groups())
    try:
        parsed = datetime(now.year, month, day, hour, minute, tzinfo=AIRPORT_TZ)
    except ValueError:
        return None

    if parsed < now - timedelta(days=180):
        return parsed.replace(year=parsed.year + 1)
    if parsed > now + timedelta(days=180):
        return parsed.replace(year=parsed.year - 1)
    return parsed


def _select_text(soup: BeautifulSoup, selector: str) -> str | None:
    element = soup.select_one(selector)
    if element is None:
        return None
    return element.get_text(" ", strip=True)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\s+", " ", value).strip() or None
