# Architektur

> Beschreibt den **tatsächlichen** Stand. Geplantes, aber nicht Umgesetztes gehört nach
> [roadmap.md](roadmap.md), Abweichungen nach [bekannte-luecken.md](bekannte-luecken.md).

## Zweck und Abgrenzung

{{PROJEKT_ZWECK}}

**Nicht** Aufgabe dieses Projekts:

- <Was bewusst außerhalb liegt — verhindert schleichenden Scope-Zuwachs>

## Tech-Stack

| Schicht | Technologie | Warum |
|---|---|---|
| Sprache / Laufzeit | {{TECH_STACK}} | <Begründung, oder Verweis auf D-xxx> |
| Persistenz | <…> | <…> |
| Schnittstelle | <…> | <…> |
| Tests | <…> | <…> |

## Komponenten

```text
<Textdiagramm der Komponenten und ihrer Aufrufrichtung>

  ┌──────────┐      liest       ┌──────────┐
  │ Komp. A  │ ───────────────► │ Komp. B  │
  └──────────┘                  └──────────┘
```

| Komponente | Verantwortung | Darf nicht |
|---|---|---|
| <Name> | <eine Aufgabe> | <was ausdrücklich Aufgabe einer anderen Komponente ist> |

Regel: Keine Komponente übernimmt Aufgaben einer anderen. Verschiebt sich eine Verantwortung,
ist das eine Design-Entscheidung → [design-entscheidungen.md](design-entscheidungen.md).

## Datenfluss

<Weg der Daten von der Quelle bis zur Ausgabe, mit den Stellen, an denen validiert oder
persistiert wird. Schema und Verträge nicht hier ausbreiten, sondern verlinken:>

Details zu Formaten: [datenmodell.md](datenmodell.md).
Details zu Endpunkten: [api-referenz.md](api-referenz.md).

## Verzeichnisstruktur

```text
{{QUELLCODE_ORDNER}}/
├── <modul>/          # <Aufgabe>
└── <modul>/          # <Aufgabe>
```

## Invarianten

Zusagen, auf die sich der gesamte Code verlässt. Wer eine davon bricht, bricht das System:

1. <z. B. „IDs sind unveränderlich und nie ein Dateipfad">
2. <z. B. „Schreibende Zugriffe erfolgen ausschließlich über Komponente X">
3. <z. B. „Ausgaben werden atomar geschrieben: temporäre Datei, dann umbenennen">

## Start und Betrieb

```bash
{{INSTALL_BEFEHL}}
{{BUILD_BEFEHL}}
```

Konfiguration: [konfiguration.md](konfiguration.md).
