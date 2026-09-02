# Datenmodell

> Enthält nur, was **wirklich** persistiert oder zwischen Komponenten ausgetauscht wird.
> Trifft auf dieses Projekt nichts davon zu: Datei löschen und aus
> [README.md](README.md) austragen.

## Identitäten

| Bezeichner | Bedeutung | Vergeben von | Unveränderlich |
|---|---|---|---|
| `<id>` | <…> | <Komponente> | ja/nein |

Grundsatz: Dateipfade und Positionen in einer Liste sind **nie** ein Primärschlüssel. Ein
verschobener Datensatz muss über seine ID wiedererkennbar bleiben.

Erlaubte Zeichen in IDs: Buchstaben, Zahlen, Punkt, Unterstrich, Bindestrich — vor jeder
Pfadbildung geprüft (siehe [sicherheit-datenschutz.md](sicherheit-datenschutz.md)).

## Schema

```text
<Tabellen bzw. Dokumentstruktur mit Feldern und Typen>
```

| Feld | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| <…> | <…> | ja/nein | <…> |

## Datenverträge

Regeln für Formate, die zwischen Komponenten ausgetauscht werden:

- Jede Ausgabe trägt eine `schema_version`.
- **Erzeuger sind strikt:** nur belegbare Werte und dokumentierte Typen schreiben.
- **Verbraucher sind tolerant** gegenüber neuen Feldern und **strikt** gegenüber unbekannten
  Hauptversionen — lieber verweigern als falsch interpretieren.
- `null` bedeutet „nicht verfügbar", `0` bedeutet einen gemessenen Nullwert. Die beiden werden nie
  vermischt.
- Schätzungen werden als Schätzung gekennzeichnet, nie als Messwert ausgegeben.
- Schreibvorgänge sind atomar: temporäre Datei schreiben, dann umbenennen.

## Migrationen

- Migrationen sind vorwärts ausführbar, idempotent und getestet.
- Eine Migration wird nie nachträglich verändert — Korrektur erfolgt über eine neue Migration.

Ändert sich ein Datenvertrag, müssen im **selben** Arbeitspaket geändert werden:

1. Schema-Definition im Code
2. alle lesenden Stellen und deren unterstützte Hauptversionen
3. Testfixtures
4. diese Datei
