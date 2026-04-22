"""Constants for the FRA Betriebsrichtung integration."""

from datetime import timedelta

DOMAIN = "fra_betriebsrichtung"

EVENT_DIRECTION_CHANGED = f"{DOMAIN}_direction_changed"

CONF_NOISE_DIRECTION = "noise_direction"
CONF_WARNING_MINUTES = "warning_minutes"

DIRECTION_BR07 = "BR 07"
DIRECTION_BR25 = "BR 25"
DIRECTION_OPTIONS = (DIRECTION_BR07, DIRECTION_BR25)
DEFAULT_NOISE_DIRECTION = DIRECTION_BR07
DEFAULT_WARNING_MINUTES = 60
MAX_WARNING_MINUTES = 360
MIN_WARNING_MINUTES = 0
WARNING_MINUTES_STEP = 5

SERVICE_REFRESH = "refresh"

UPDATE_INTERVAL = timedelta(minutes=30)

UMWELTHAUS_URL = (
    "https://www.umwelthaus.org/fluglaerm/anwendungen-service/"
    "aktuelle-betriebsrichtung-und-prognose/"
)
FALLBACK_URL = "https://betriebsrichtungsprognose.de/frankfurt-fra/"

SOURCE_UMWELTHAUS = "Umwelthaus"
SOURCE_FALLBACK = "betriebsrichtungsprognose.de"

ATTR_CURRENT_SINCE = "current_since"
ATTR_CURRENT_SINCE_START = "current_since_start"
ATTR_CURRENT_DURATION_MINUTES = "current_duration_minutes"
ATTR_CURRENT_DIRECTION = "current_direction"
ATTR_DATE = "date"
ATTR_DIRECTION = "direction"
ATTR_END = "end"
ATTR_ERRORS = "errors"
ATTR_FALLBACK_OK = "fallback_ok"
ATTR_FALLBACK_USED = "fallback_used"
ATTR_FORECAST_DIRECTION = "forecast_direction"
ATTR_FROM = "from"
ATTR_LABEL = "label"
ATTR_LAST_UPDATE = "last_update"
ATTR_LAST_SUCCESS = "last_success"
ATTR_NEW_DIRECTION = "new_direction"
ATTR_NEXT_SLOT = "next_slot"
ATTR_NEXT_SLOT_LABEL = "next_slot_label"
ATTR_NOISE_DIRECTION = "noise_direction"
ATTR_PRIMARY_OK = "primary_ok"
ATTR_SLOTS = "slots"
ATTR_SOURCE = "source"
ATTR_STARTS_IN_MINUTES = "starts_in_minutes"
ATTR_SUMMARY = "summary"
ATTR_TO = "to"
ATTR_WARNING_MINUTES = "warning_minutes"
