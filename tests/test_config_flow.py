"""Config flow tests for FRA Betriebsrichtung."""

from __future__ import annotations

from custom_components.fra_betriebsrichtung.config_flow import _options_schema
from custom_components.fra_betriebsrichtung.const import (
    CONF_NOISE_DIRECTION,
    CONF_WARNING_MINUTES,
    DEFAULT_WARNING_MINUTES,
    DIRECTION_BR25,
)


def test_options_schema_uses_warning_default() -> None:
    """Setup/options schema includes the warning window default."""
    values = _options_schema()({})

    assert values[CONF_NOISE_DIRECTION] == "br_07"
    assert values[CONF_WARNING_MINUTES] == DEFAULT_WARNING_MINUTES


def test_options_schema_preserves_options_flow_warning_value() -> None:
    """Options schema uses the stored warning window value."""
    values = _options_schema(DIRECTION_BR25, 120)({})

    assert values[CONF_NOISE_DIRECTION] == "br_25"
    assert values[CONF_WARNING_MINUTES] == 120
