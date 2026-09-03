# Konfiguration

## Umgebungsvariablen

Keine. Dieses Projekt läuft als Teil von Home Assistant und wird **nicht** über `.env`/Umgebungs-
variablen konfiguriert, sondern ausschließlich über die HA-eigene Config-Entry-UI
(`config_flow.py`) — pro physischem Speicher ein Entry mit Host/IP, Port, Hersteller/Protokoll und
optional einem `hems_entity_prefix` (aktiviert die eingebaute HEMS-Anbindung, siehe
[api-referenz.md](api-referenz.md), leer = deaktiviert). HA speichert diese Werte selbst
(`.storage/core.config_entries`), diese Integration verwaltet keinen eigenen Konfigurationsspeicher.

## Konfigurationsdateien

| Datei | Zweck | Eingecheckt |
|---|---|---|
| `custom_components/battery_bridge/manifest.json` | Version und Metadaten | ja |
| `custom_components/battery_bridge/strings.json` / `translations/de.json` | Config-Flow- und Entity-Texte | ja |
| `hacs.json` | HACS-Metadaten für die Verteilung | ja |

## Secrets

- Es werden aktuell keine Secrets verwaltet: Marstek Local API läuft unauthentifiziert im LAN
  (kein API-Key, kein Passwort) — siehe [sicherheit-datenschutz.md](sicherheit-datenschutz.md).
- Bräuchte ein künftiger Adapter (z. B. eine Cloud-Anbindung) doch Zugangsdaten, laufen die über
  den verschlüsselten Storage von Home Assistant (Config-Entry-Daten), **nie** über Code oder eine
  eingecheckte Datei. Das ist dann eine Design-Entscheidung → [design-entscheidungen.md](design-entscheidungen.md).
- Ein versehentlich geloggter Wert aus einer Herstellerantwort wird vor dem Log maskiert, falls
  sich das je ändert — aktuell enthält die Marstek-Antwort keine Zugangsdaten.

## Grundsatz

Alles, was sich zwischen Umgebungen unterscheidet (Pfade, Hosts, Zeitintervalle, Grenzwerte), ist
konfigurierbar und hat einen sinnvollen Default. Fest verdrahtete Werte im Code sind ein Fehler,
kein Feature.
