"""Data models for FRA Betriebsrichtung."""

from __future__ import annotations

from dataclasses import dataclass, field


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
class SourceHealth:
    """Source status from the latest successful update."""

    primary_ok: bool | None = None
    fallback_ok: bool | None = None
    fallback_used: bool = False
    last_success: str | None = field(default=None, compare=False)
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class FraBetriebsrichtungData:
    """Normalized operating direction data."""

    current_direction: str | None = None
    current_label: str | None = None
    current_since: str | None = None
    current_since_start: str | None = None
    current_duration_minutes: int | None = None
    forecast_summary: str | None = None
    forecast_slots: tuple[ForecastSlot, ...] = ()
    source: str | None = None
    last_update: str | None = None
    health: SourceHealth = field(default_factory=SourceHealth)

    @property
    def primary_ok(self) -> bool | None:
        """Return whether the primary source was usable."""
        return self.health.primary_ok

    @property
    def fallback_ok(self) -> bool | None:
        """Return whether the fallback source was usable."""
        return self.health.fallback_ok

    @property
    def fallback_used(self) -> bool:
        """Return whether fallback data is part of the normalized result."""
        return self.health.fallback_used

    @property
    def last_success(self) -> str | None:
        """Return the last successful coordinator update time."""
        return self.health.last_success

    @property
    def errors(self) -> tuple[str, ...]:
        """Return recoverable source errors from the last successful update."""
        return self.health.errors

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
