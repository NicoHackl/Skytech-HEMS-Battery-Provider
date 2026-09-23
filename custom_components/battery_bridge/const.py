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

# Hersteller/Protokoll als stabile IDs (Regel: Hersteller × Protokoll, siehe D-006). Ein weiterer
# Adapter braucht hier nur einen neuen Eintrag, keine Umstellung des Config-Flows.
MANUFACTURER_MARSTEK: Final = "marstek"
PROTOCOL_MARSTEK_UDP: Final = "marstek_udp"
MANUFACTURER_E3DC: Final = "e3dc"
PROTOCOL_E3DC_RSCP: Final = "e3dc_rscp"

# Anzeigename je Hersteller, für device_info und die Herstellerauswahl im Config-Flow — die
# Konstanten oben bleiben stabile IDs.
MANUFACTURER_NAMES: Final[dict[str, str]] = {
    MANUFACTURER_MARSTEK: "Marstek",
    MANUFACTURER_E3DC: "E3DC",
}

# E3DC-RSCP-Zugang (D-015): RSCP-Schlüssel, wie er am Hauskraftwerk selbst hinterlegt ist.
# Benutzername/Passwort nutzen die HA-Konstanten CONF_USERNAME/CONF_PASSWORD.
CONF_RSCP_KEY: Final = "rscp_key"
E3DC_RSCP_DEFAULT_PORT: Final = 5033

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

# Keep-Alive-Takt der HEMS-Anbindung für Marstek (hems_bridge.py, D-012) — seit D-015 liefert
# jeder Adapter seinen eigenen Takt (`StorageAdapter.keepalive_interval`). Deutlich unter dem
# Marstek-Passive-Mode-Watchdog `_PASSIVE_MODE_DURATION_S` (300 s, adapters/marstek_udp.py) —
# sonst würde ein Gerät-Timeout die Sicherheitsmarge komplett aufbrauchen, bevor der nächste
# Keep-Alive überhaupt drankäme.
HEMS_KEEPALIVE_INTERVAL: Final = timedelta(seconds=60)

# Keep-Alive-Takt der HEMS-Anbindung für E3DC (D-015): E3DC übernimmt nach rund 10 s ohne neuen
# Sollwert (RSCP EMS_REQ_SET_POWER) selbst wieder die Regelung. 5 s lässt einen verpassten Takt
# zu, bevor das passiert.
E3DC_KEEPALIVE_INTERVAL: Final = timedelta(seconds=5)
