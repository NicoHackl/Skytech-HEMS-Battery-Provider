# Konfiguration

## Umgebungsvariablen

Keine. Dieses Projekt läuft als Teil von Home Assistant und wird **nicht** über `.env`/Umgebungs-
variablen konfiguriert, sondern ausschließlich über die HA-eigene Config-Entry-UI
(`config_flow.py`) — pro physischem Speicher ein Entry mit Host/IP, Port, Hersteller/Protokoll und
optional einem `hems_entity_prefix` (aktiviert die eingebaute HEMS-Anbindung, siehe
[api-referenz.md](api-referenz.md), leer = deaktiviert). HA speichert diese Werte selbst
(`.storage/core.config_entries`), diese Integration verwaltet keinen eigenen Konfigurationsspeicher.

Das Abfrageintervall (`update_interval_seconds`, D-014) wird beim Einrichten mit abgefragt —
Default 5 Sekunden, erlaubter Bereich 1–60 Sekunden, ganzzahlig — und liegt in `entry.options`,
nicht `entry.data`. Über den Options-Flow des Entries (Zahnrad-Symbol in der HA-Oberfläche) lässt
es sich jederzeit nachträglich ändern, ohne das Gerät neu einzurichten; der Entry lädt sich dabei
automatisch neu, die Änderung wirkt ohne HA-Neustart. Bestandsgeräte ohne gesetzten Wert laufen
mit dem Default (5 s).

Mit HEMS-Anbindung zeigt der Options-Flow zusätzlich `hems_timeout_factor` (D-016): Frist ohne
HEMS-Lebenszeichen als Vielfaches der HEMS-Zykluszeit, Default 3, erlaubt 2–10, ganzzahlig. Ohne
Angabe des Intervalls durch das HEMS gilt eine feste Frist von 90 s.

## Konfigurationsdateien

| Datei | Zweck | Eingecheckt |
|---|---|---|
| `custom_components/battery_bridge/manifest.json` | Version und Metadaten | ja |
| `custom_components/battery_bridge/strings.json` / `translations/de.json` | Config-Flow- und Entity-Texte | ja |
| `hacs.json` | HACS-Metadaten für die Verteilung | ja |

## Secrets

- Marstek Local API läuft unauthentifiziert im LAN (kein API-Key, kein Passwort) — siehe
  [sicherheit-datenschutz.md](sicherheit-datenschutz.md).
- E3DC (RSCP, D-015) braucht Benutzername und Passwort des E3DC-Portalkontos sowie den am
  Hauskraftwerk hinterlegten RSCP-Schlüssel. Alle drei werden im Config-Flow eingegeben
  (Passwort und Schlüssel maskiert) und liegen ausschließlich in den Config-Entry-Daten von Home
  Assistant — **nie** im Code, in einer eingecheckten Datei oder im Log. Fehlermeldungen des
  Adapters nennen nur Host, Port und Fehlertyp.
- Ein versehentlich geloggter Wert aus einer Herstellerantwort wird vor dem Log maskiert, falls
  sich das je ändert — aktuell enthalten weder Marstek- noch E3DC-Antworten Zugangsdaten.

## Config-Flow-Felder je Hersteller

| Hersteller | Felder | Default |
|---|---|---|
| Marstek (UDP) | Anzeigename, IP-Adresse, UDP-Port, HEMS-Präfix, Abfrageintervall | Port 30000, 5 s |
| E3DC (RSCP) | Anzeigename, IP-Adresse, Port, E3DC-Benutzername, E3DC-Passwort, RSCP-Schlüssel, HEMS-Präfix, Abfrageintervall | Port 5033, 5 s |

HEMS-Keep-Alive-Takt (nicht konfigurierbar, geräteabhängig): Marstek 60 s, E3DC 5 s (D-015).

## Grundsatz

Alles, was sich zwischen Umgebungen unterscheidet (Pfade, Hosts, Zeitintervalle, Grenzwerte), ist
konfigurierbar und hat einen sinnvollen Default. Fest verdrahtete Werte im Code sind ein Fehler,
kein Feature.
