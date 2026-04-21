"""Constants for the FRA Betriebsrichtung integration."""

from datetime import timedelta

DOMAIN = "fra_betriebsrichtung"

CONF_NOISE_DIRECTION = "noise_direction"

DIRECTION_BR07 = "BR 07"
DIRECTION_BR25 = "BR 25"
DIRECTION_OPTIONS = (DIRECTION_BR07, DIRECTION_BR25)
DEFAULT_NOISE_DIRECTION = DIRECTION_BR07

UPDATE_INTERVAL = timedelta(minutes=30)

UMWELTHAUS_URL = (
    "https://www.umwelthaus.org/fluglaerm/anwendungen-service/"
    "aktuelle-betriebsrichtung-und-prognose/"
)
FALLBACK_URL = "https://betriebsrichtungsprognose.de/frankfurt-fra/"

SOURCE_UMWELTHAUS = "Umwelthaus"
SOURCE_FALLBACK = "betriebsrichtungsprognose.de"

ATTR_CURRENT_SINCE = "current_since"
ATTR_CURRENT_DIRECTION = "current_direction"
ATTR_LABEL = "label"
ATTR_LAST_UPDATE = "last_update"
ATTR_NOISE_DIRECTION = "noise_direction"
ATTR_SLOTS = "slots"
ATTR_SOURCE = "source"
ATTR_SUMMARY = "summary"

