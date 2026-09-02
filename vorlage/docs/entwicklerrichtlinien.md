# Entwicklerrichtlinien

> Sprachregeln (Code englisch, Text deutsch) und Secrets-Verbot stehen in
> [`AGENTS.md`](../AGENTS.md) und werden hier **nicht** wiederholt. Hier steht nur, was darüber
> hinausgeht. Alles, was ein Mensch am Ende liest — Meldungen, Ausgaben, Oberflächentexte —
> steht in [nutzertexte.md](nutzertexte.md).

## Naming

| Element | Konvention | Beispiel |
|---|---|---|
| Variablen, Funktionen | {{NAMING_FUNKTIONEN}} | `calculate_total_power` |
| Klassen, Typen | PascalCase | `DeviceController` |
| Konstanten | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| Dateien / Module | {{NAMING_DATEIEN}} | `device_controller.py` |
| Booleans | Frage-Präfix `is_` / `has_` / `can_` | `is_enabled`, `has_permission` |

Abkürzungen nur, wenn sie in der Domäne etabliert sind. `cfg` statt `config` ist keine Ersparnis,
die den Verlust an Lesbarkeit rechtfertigt.

## Projektstruktur

```text
{{PROJEKT_NAME}}/
├── {{QUELLCODE_ORDNER}}/     # Produktivcode
├── tests/                    # Tests, Struktur spiegelt den Quellcode
└── docs/                     # diese Doku
```

Regel: Eine Datei hat **eine** Verantwortlichkeit. Wächst eine Datei über ~400 Zeilen, ist das ein
Hinweis auf eine fehlende Trennung — kein Automatismus, aber ein Prüfanlass.

## Kommentare

- Kommentare erklären das **Warum**, nicht das Was. `i = i + 1  # i um eins erhöhen` ist wertlos.
- Öffentliche Funktionen bekommen einen Docstring: Zweck, Parameter, Rückgabe, geworfene Fehler.
- Auskommentierter Code wird **gelöscht**, nicht aufbewahrt. Dafür gibt es Git.
- `TODO`-Kommentare bekommen einen Verweis: `# TODO(D-007): …` oder eine Issue-Nummer. Ein
  namenloses `TODO` verschwindet und wird nie erledigt.

## Fehlerbehandlung

- Fehler werden **nicht stillschweigend verschluckt**. Kein leerer `catch`/`except`-Block.
- Fehlermeldungen für den User: deutsch, konkret, mit Handlungsanweisung.
  Schlecht: „Fehler aufgetreten". Gut: „Konfigurationsdatei `config.yaml` nicht gefunden — erwartet
  im Repo-Root."
- **Technische Details gehören ins Log, nicht in die Ausgabe an den User** — eiserne Regel 12.
  Konkret nie sichtbar: Statuscode, Exception-Klasse, Stacktrace, Datenbank- oder Dateipfad,
  SQL, interner Zustandsname, technische ID. Jeder Fehler wird **zuerst vollständig geloggt**,
  dann in einen Satz übersetzt, den der User versteht und aus dem hervorgeht, was er tun kann.
  Was genau wie formuliert wird: [nutzertexte.md](nutzertexte.md).
- Ein technisches Detail, das der User zum Melden braucht, wird zu **einer** kurzen Kennung
  (Fehlernummer), die im Log denselben Vorgang identifiziert — nicht zum Rohtext auf dem Schirm.
- Externe Aufrufe (Netzwerk, Dateisystem, fremde APIs) bekommen ein explizites Timeout und
  definiertes Verhalten im Fehlerfall.

## Logging

| Level | Wofür |
|---|---|
| `DEBUG` | Entwicklungsdetails, im Normalbetrieb aus |
| `INFO` | Normale Zustandsübergänge, Start/Stop, abgeschlossene Vorgänge |
| `WARNING` | Unerwartet, aber automatisch behandelt |
| `ERROR` | Vorgang fehlgeschlagen, Eingriff nötig |

Nie geloggt werden: Passwörter, Tokens, API-Keys, personenbezogene Daten. Siehe
[sicherheit-datenschutz.md](sicherheit-datenschutz.md).

## Abhängigkeiten

- Neue Abhängigkeit nur, wenn sie mehr Aufwand spart, als sie an Wartung kostet. Eine
  10-Zeilen-Hilfsfunktion rechtfertigt kein zusätzliches Paket.
- Versionen werden gepinnt ({{LOCKFILE}}).
- Eine neue Laufzeit-Abhängigkeit ist eine Design-Entscheidung → Eintrag in
  [design-entscheidungen.md](design-entscheidungen.md).

## Formatierung

Formatierung erledigt das Tooling, nicht die Diskussion: `{{LINT_BEFEHL}}`. Manuelles Abweichen vom
Formatter ist kein zulässiger Diff-Inhalt — er verrauscht Reviews.
