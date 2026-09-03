"""Konstanten der Battery-Bridge-Integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "battery_bridge"

# Vom User im Config-Flow vergebener Anzeigename, aus dem der Entity-Präfix entsteht.
CONF_DISPLAY_NAME: Final = "display_name"
CONF_MANUFACTURER: Final = "manufacturer"
CONF_PROTOCOL: Final = "protocol"

# Optional: HEMS-Geräte-Präfix für die eingebaute HEMS-Anbindung (siehe hems_bridge.py, D-009).
# Leer/fehlend heißt: dieser Speicher wird nicht von SkytechHEMS gesteuert, nur Entities liefern.
CONF_HEMS_ENTITY_PREFIX: Final = "hems_entity_prefix"

# Bisher einziger Hersteller/Protokoll — Auswahl im Config-Flow trotzdem als Select,
# damit ein zweiter Adapter (Regel: Hersteller × Protokoll, siehe D-006) keine
# Flow-Umstellung braucht, nur einen neuen Eintrag in MANUFACTURERS.
MANUFACTURER_MARSTEK: Final = "marstek"
PROTOCOL_MARSTEK_UDP: Final = "marstek_udp"

# Anzeigename je Hersteller, für device_info — die Konstanten oben bleiben stabile IDs.
MANUFACTURER_NAMES: Final[dict[str, str]] = {
    MANUFACTURER_MARSTEK: "Marstek",
}

MARSTEK_UDP_DEFAULT_PORT: Final = 30000
# Marstek erlaubt laut App eine Portänderung im Bereich 49152–65535.
MARSTEK_UDP_PORT_RANGE: Final = (1, 65535)

DEFAULT_UPDATE_INTERVAL: Final = timedelta(seconds=5)
