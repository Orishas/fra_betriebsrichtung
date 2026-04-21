"""HTML parsers for FRA operating direction data."""

from __future__ import annotations

from dataclasses import dataclass
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

AIRPORT_TZ = ZoneInfo("Europe/Berlin")

_BR07_RE = re.compile(r"\b(?:BR|Betriebsrichtung)\s*0?7\b|\b07\s*\(Ost\)", re.I)
_BR25_RE = re.compile(r"\b(?:BR|Betriebsrichtung)\s*25\b|\b25\s*\(West\)", re.I)


@dataclass(frozen=True)
class ForecastSlot:
    """A normalized forecast period."""

    start: str
    end: str
    direction: str
    date: str | None = None
    start_iso: str | None = None
    end_iso: str | None = None

    def as_dict(self) -> dict[str, str]:
        """Return the Home Assistant attribute representation."""
        values = {"from": self.start, "to": self.end, "direction": self.direction}
        if self.date:
            values["date"] = self.date
        if self.start_iso:
            values["start"] = self.start_iso
        if self.end_iso:
            values["end"] = self.end_iso
        return values


@dataclass(frozen=True)
class FraBetriebsrichtungData:
    """Normalized operating direction data."""

    current_direction: str | None = None
    current_label: str | None = None
    current_since: str | None = None
    forecast_summary: str | None = None
    forecast_slots: tuple[ForecastSlot, ...] = ()
    source: str | None = None
    last_update: str | None = None

    @property
    def has_current(self) -> bool:
        """Return whether current direction data is available."""
        return self.current_direction is not None

    @property
    def has_forecast(self) -> bool:
        """Return whether forecast data is available."""
        return self.forecast_summary is not None or bool(self.forecast_slots)

    @property
    def has_any_data(self) -> bool:
        """Return whether this object contains any useful data."""
        return self.has_current or self.has_forecast


def parse_umwelthaus(html: str) -> FraBetriebsrichtungData | None:
    """Parse the Umwelthaus operating direction page."""
    soup = BeautifulSoup(html, "html.parser")

    current_label = _clean_text(_select_text(soup, "figure.br-display-br h4"))
    current_direction = normalize_direction(current_label)
    current_since = _parse_current_since(soup)

    forecast_summary = _clean_text(_select_text(soup, "#brp p.introtext"))
    last_update = _parse_last_update(forecast_summary)
    forecast_slots = _parse_umwelthaus_slots(soup)

    data = FraBetriebsrichtungData(
        current_direction=current_direction,
        current_label=current_label,
        current_since=current_since,
        forecast_summary=forecast_summary,
        forecast_slots=forecast_slots,
        source=SOURCE_UMWELTHAUS,
        last_update=last_update,
    )
    return data if data.has_any_data else None


def parse_fallback(html: str) -> FraBetriebsrichtungData | None:
    """Parse the betriebsrichtungsprognose.de fallback page."""
    labels = _parse_js_array(html, r"labels:\s*(\[[^\]]+\])")
    values = _parse_js_array(html, r"var\s+abflugData\s*=\s*(\[[^\]]+\])")
    if not labels or not values:
        return None

    slots: list[ForecastSlot] = []
    count = min(len(labels), len(values))
    for index in range(count):
        direction = _direction_from_fallback_value(values[index])
        if direction is None:
            continue
        start_dt = _datetime_from_fallback_label(labels[index])
        end_dt = None
        if start_dt:
            end_dt = (
                _datetime_from_fallback_label(labels[index + 1])
                if index + 1 < count
                else start_dt + timedelta(hours=3)
            )
        if start_dt and end_dt:
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
            continue

        start = _time_from_fallback_label(labels[index])
        end = (
            _time_from_fallback_label(labels[index + 1])
            if index + 1 < count
            else _add_hours_to_time(start, 3)
        )
        if start and end:
            slots.append(ForecastSlot(start=start, end=end, direction=direction))

    summary = None
    if slots:
        first = slots[0]
        summary = f"{first.direction} ab {first.start}"

    data = FraBetriebsrichtungData(
        forecast_summary=summary,
        forecast_slots=tuple(slots),
        source=SOURCE_FALLBACK,
    )
    return data if data.has_any_data else None


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
        source = f"{primary.source}; {fallback.source}" if primary.source else fallback.source

    return FraBetriebsrichtungData(
        current_direction=primary.current_direction or fallback.current_direction,
        current_label=primary.current_label or fallback.current_label,
        current_since=primary.current_since or fallback.current_since,
        forecast_summary=primary.forecast_summary or fallback.forecast_summary,
        forecast_slots=primary.forecast_slots or fallback.forecast_slots,
        source=source,
        last_update=primary.last_update or fallback.last_update,
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


def _direction_from_fallback_value(value: Any) -> str | None:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    if numeric_value > 0:
        return DIRECTION_BR07
    if numeric_value < 0:
        return DIRECTION_BR25
    return None


def _parse_js_array(html: str, pattern: str) -> list[Any] | None:
    match = re.search(pattern, html, flags=re.S)
    if not match:
        return None
    return json.loads(match.group(1))


def _time_from_fallback_label(label: Any) -> str | None:
    if not isinstance(label, str):
        return None
    match = re.search(r"(\d{2}:\d{2})$", label.strip())
    return match.group(1) if match else None


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


def _add_hours_to_time(value: str | None, hours: int) -> str | None:
    if value is None:
        return None
    parsed = datetime.strptime(value, "%H:%M")
    return (parsed + timedelta(hours=hours)).strftime("%H:%M")


def _select_text(soup: BeautifulSoup, selector: str) -> str | None:
    element = soup.select_one(selector)
    if element is None:
        return None
    return element.get_text(" ", strip=True)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\s+", " ", value).strip() or None
