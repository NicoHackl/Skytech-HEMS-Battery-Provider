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

# Poll-Intervall in Sekunden — pro Entry in `entry.options` gespeichert, im Config-Flow
# gesetzt und im Options-Flow nachträglich änderbar (D-014). Kein Teil von `entry.data`,
# da nur Options-Änderungen den bestehenden Entry automatisch neu laden (siehe __init__.py).
CONF_UPDATE_INTERVAL: Final = "update_interval_seconds"

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

# Default/Grenzen für CONF_UPDATE_INTERVAL (D-014). 5 s statt vormals fix 1 s, da der
# 1-s-Takt zu Aussetzern am Speicher-Chip führte; 1–60 s deckt normale Poll-Fälle ab und
# schließt Fehleingaben (z. B. Minuten/Stunden) aus.
DEFAULT_UPDATE_INTERVAL_SECONDS: Final = 5
MIN_UPDATE_INTERVAL_SECONDS: Final = 1
MAX_UPDATE_INTERVAL_SECONDS: Final = 60

# Poll-Takt, solange das Gerät nicht antwortet (coordinator.py). Ein Speicher, der gerade nicht
# antwortet, wird nicht weiter im Normaltakt mit je drei Versuchen beschickt — das hilft niemandem
# und belastet den Netzwerkteil des Geräts weiter. Bleibt weit unter dem 300-s-Watchdog des
# Passive-Mode, ein erholtes Gerät wird also spätestens eine halbe Minute später wieder erkannt.
FAILED_UPDATE_INTERVAL: Final = timedelta(seconds=30)

# Keep-Alive-Takt der HEMS-Anbindung (hems_bridge.py, D-012): deutlich unter dem
# Marstek-Passive-Mode-Watchdog `_PASSIVE_MODE_DURATION_S` (300 s, adapters/marstek_udp.py) —
# sonst würde ein Gerät-Timeout die Sicherheitsmarge komplett aufbrauchen, bevor der nächste
# Keep-Alive überhaupt drankäme.
HEMS_KEEPALIVE_INTERVAL: Final = timedelta(seconds=60)
