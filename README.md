# Skytech HEMS Battery Provider

Home-Assistant-Integration, die Batteriespeicher verschiedener Hersteller (Marstek zuerst) einheitlich als normalisierte HA-Entitäten bereitstellt: Ist-SoC und Ist-Lade-/Entladeleistung lesen, Soll-Lade-/Entladeleistung schreiben. Brücke zwischen Herstelleranbindung und generischen Verbrauchern wie SkytechHEMS.

## Schnellstart

```bash
uv sync
pytest
ruff check .
```

## Nutzung

Installation über HACS (custom repository) oder manuell nach `custom_components/battery_bridge`
kopieren, Home Assistant neu starten. Danach in **Einstellungen → Geräte & Dienste → Integration
hinzufügen** nach „Skytech HEMS Battery Provider" suchen, Hersteller wählen (aktuell Marstek), Verbindungsdaten
eingeben. Pro physischem Speicher wird der Vorgang einmal wiederholt. Die entstehenden Entities
(SoC, Ist-/Soll-Lade-/Entladeleistung — Details: [docs/api-referenz.md](docs/api-referenz.md))
lassen sich wie jede andere HA-Entity in Dashboards, Automationen oder als Quelle für
[SkytechHEMS](https://github.com/Skytech-Energy-Solutions) verwenden.

Wird dieser Speicher von SkytechHEMS gesteuert, im selben Einrichtungsschritt das
**SkytechHEMS-Präfix** eintragen (z. B. `acspeicher1`) — die Integration übersetzt dann die
HEMS-Anforderungshelfer selbst laufend in Soll-Lade-/Entladeleistung, es ist keine zusätzliche
Home-Assistant-Automation nötig. Leer lassen für reine Entity-Nutzung ohne SkytechHEMS.

**Schreibzugriff (Soll-Leistung) ist noch nicht an echter Hardware getestet** — vor dem ersten
produktiven Einsatz erst mit einem kleinen Sollwert prüfen, siehe
[docs/bekannte-luecken.md](docs/bekannte-luecken.md).

## Entwicklung

```bash
pytest      # Tests
ruff check .      # Linting
```

Vor dem ersten Commit lesen: [CONTRIBUTING.md](CONTRIBUTING.md).

## Dokumentation

| Wofür | Wo |
|---|---|
| Verbindliche Projektregeln (Menschen **und** KI-Agenten) | [AGENTS.md](AGENTS.md) |
| Technische Referenz | [docs/README.md](docs/README.md) |
| Änderungen je Version | [CHANGELOG.md](CHANGELOG.md) |

## Lizenz

Noch nicht festgelegt — offener Punkt, siehe [docs/roadmap.md](docs/roadmap.md).
