# D-014: Poll-Intervall pro Speicher konfigurierbar (Config-Flow + Options-Flow)

- **Datum:** 12.09.2026
- **Status:** Aktiv
- **Betrifft:** `const.py`, `config_flow.py`, `coordinator.py`, `__init__.py`, `strings.json`,
  `translations/de.json`, `tests/conftest.py`, `tests/test_config_flow.py`,
  `tests/test_options_flow.py`, `tests/test_coordinator.py`

## Kontext

Der Poll-Takt lief bislang als globaler Fixwert `DEFAULT_UPDATE_INTERVAL` (1 s, siehe
`bekannte-luecken.md`) — für alle Speicher gleich, nur im Code änderbar. D-013 dokumentiert den
Verdacht, dass genau dieser 1-s-Takt zu Aussetzern am Netzwerkteil des Marstek-Chips führt: ein
erfolgloser Poll blockiert bereits drei Sekunden, derselbe `_call_lock` trägt zusätzlich die
HEMS-Schreibvorgänge.

Der User hat inzwischen eine eigene, außerhalb dieser Integration liegende Alternativlösung, um
die Leistung schnell abzufragen — der reguläre Poll-Takt dieser Integration muss diese
Geschwindigkeit also nicht mehr liefern und kann entspannter laufen. Zugleich soll der Takt nicht
für alle Speicher gleich fest verdrahtet bleiben: unterschiedliche Geräte oder Netzwerksituationen
können unterschiedliche Werte vertragen (Grundsatz „Zeitintervalle sind konfigurierbar",
`konfiguration.md`).

## Betrachtete Optionen

### Option A — Feld im Config-Flow, änderbar über einen Options-Flow (gewählt)

- Dafür: Deckt beide Anforderungen ab — Wert bei der Einrichtung mitgeben, später ohne
  Neuanlage des Geräts ändern. Options-Flow ist der von Home Assistant vorgesehene Weg für genau
  diesen Fall.
- Dagegen: Zwei Flow-Klassen statt einer, ein zusätzlicher `update_listener` für den Reload.

### Option B — Nur ein Feld im Config-Flow, Änderung ausschließlich durch Löschen/Neuanlage des Entry

- Dafür: Kein Options-Flow nötig, weniger Code.
- Dagegen: Verletzt die zweite Anforderung des Users direkt („nachträglich ändern können") — ein
  Speicher neu einzurichten, nur um den Takt zu ändern, wirft Entity-Historie und HEMS-Präfix weg.

### Option C — Eigene `number`-Entity für das Intervall statt Config-/Options-Flow

- Dafür: Änderung ohne Flow-Dialog, direkt im Dashboard.
- Dagegen: Poll-Verhalten ist eine Einrichtungs-/Wartungsangelegenheit, kein Betriebswert wie
  Soll-Ladeleistung — gehört konzeptionell zur Konfiguration des Entry, nicht zu seinen Entities.
  Home Assistant sieht dafür ausdrücklich den Options-Flow vor.

## Entscheidung

Option A. Das Feld `update_interval_seconds` (`CONF_UPDATE_INTERVAL`) wird im zweiten
Config-Flow-Schritt (`marstek_udp`) mit abgefragt — Default 5 s, erlaubter Bereich 1–60 s,
ganzzahlig — und landet in `entry.options`, nicht `entry.data`: nur eine Änderung an `options`
löst automatisch den `update_listener`-Reload aus, ein Wert in `data` bliebe bis zum manuellen
Neuladen wirkungslos. Ein neuer `BatteryBridgeOptionsFlowHandler` zeigt denselben Feldnamen mit
dem aktuellen Wert als Default und schreibt eine Änderung wieder in `entry.options`.
`__init__.py` liest den Wert beim Entry-Setup, reicht ihn als `timedelta` an
`BatteryBridgeCoordinator` durch und registriert einen `update_listener`, der den Entry bei einer
Options-Änderung per `hass.config_entries.async_reload()` neu lädt — die Änderung wirkt ohne
HA-Neustart.

Die Bereichsprüfung (1–60 s) läuft manuell im Flow-Schritt, nicht über `vol.Range` im Schema: ein
dort ausgelöstes `vol.Invalid` würde Home Assistant als generischen Flow-Fehler zeigen
(`InvalidData`, siehe `homeassistant/data_entry_flow.py`), nicht als Fehler am betroffenen Feld.

Default (5 s) und Bereich (1–60 s) sind mit dem User abgestimmt, nicht geraten (Regel 7,
`AGENTS.md`).

## Folgen

- **Positiv:** Der ursprünglich in D-013 als „erster Kandidat" benannte 1-s-Takt ist kein
  Fixwert mehr — jedes Gerät läuft mit dem Takt, der zu ihm passt, änderbar ohne Neuanlage.
- **Negativ:** Bestandsgeräte ohne gesetzten Wert übernehmen beim Update automatisch den neuen
  Default (5 s statt bisher 1 s) — beabsichtigt (genau der Grund für diese Entscheidung), aber
  eine Verhaltensänderung, die im Changelog explizit benannt werden muss, nicht stillschweigend
  passieren darf.
- **Aufwand:** Neue Konstanten in `const.py`, ein Feld plus eine neue Flow-Klasse in
  `config_flow.py`, ein Konstruktor-Parameter in `coordinator.py`, ein `update_listener` in
  `__init__.py`, zwei synchron gehaltene Übersetzungsdateien, neue/angepasste Tests in
  `test_config_flow.py`, `test_options_flow.py` (neu) und `test_coordinator.py`.

## Rücknahmebedingung

Treten weiterhin Aussetzer auf, obwohl ein Gerät mit einem deutlich über 5 s liegenden Intervall
läuft, ist der Poll-Takt als Ursache widerlegt — dann ist laut D-013 der nächste Kandidat der
UDP-Reconnect-Mechanismus selbst, nicht dieses Feature. Erweist sich umgekehrt selbst der Default
von 5 s noch als zu aggressiv, ist der Default anzuheben, nicht der Nutzer allein auf eine manuelle
Anpassung zu verweisen.
