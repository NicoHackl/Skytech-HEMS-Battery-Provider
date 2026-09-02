# Dokumentation — {{PROJEKT_NAME}}

Ausführliche technische Referenz. Die **verbindlichen Regeln** stehen nicht hier, sondern in
[`AGENTS.md`](../AGENTS.md) im Repo-Root. Bei Widerspruch gilt `AGENTS.md`.

Diese Doku beschreibt den **tatsächlichen Stand des Codes**, nicht die Wunschvorstellung.
Weicht die Implementierung ab, gehört das nach [bekannte-luecken.md](bekannte-luecken.md) —
nicht stillschweigend schöngeschrieben.

## Schnellstart für neue Agenten und Entwickler

1. [`AGENTS.md`](../AGENTS.md) lesen — eiserne Regeln und Befehle.
2. [architektur.md](architektur.md) lesen — Projektzweck und Grobstruktur.
3. [git-workflow.md](git-workflow.md) lesen — **bevor** irgendetwas committet wird.
4. Für die konkrete Aufgabe die passende Datei unten nachschlagen, statt zu raten.
5. [bekannte-luecken.md](bekannte-luecken.md) prüfen, bevor angenommen wird, eine hier
   beschriebene Funktion existiere bereits.

## Inhaltsverzeichnis

| Datei | Inhalt |
|---|---|
| [architektur.md](architektur.md) | Komponenten, Verantwortlichkeiten, Datenfluss, Tech-Stack, Grenzen |
| [entwicklerrichtlinien.md](entwicklerrichtlinien.md) | Naming, Projektstruktur, Fehlerbehandlung, Kommentarstil, Abhängigkeiten |
| [frontend.md](frontend.md) | Frontend-Stack, Verzeichnisstruktur, Routing, API-Client, Seiten- und Formularmuster, Hell/Dunkel, Auslieferung |
| [design-system.md](design-system.md) | Designsprachen, Tokens je Modus, Klassenkatalog, Zustände, Haltepunkte, Icons, Barrierefreiheit |
| [nutzertexte.md](nutzertexte.md) | Was der Nutzer zu sehen bekommt: Zeit- und Zahlenformate, Fehlermeldungen, Formulierung, Prüfliste |
| [git-workflow.md](git-workflow.md) | Branch-Modell, Commit-Format, Versionierung, Release-Ablauf |
| [test-strategie.md](test-strategie.md) | Testarten, Pflicht-Testfälle, Fixtures, Coverage-Ziel |
| [design-entscheidungen.md](design-entscheidungen.md) | Entscheidungs-Log D-001 … — Quelle der Wahrheit fürs „warum" |
| [adr/](adr/) | Ausführliche Architecture Decision Records zu einzelnen Entscheidungen |
| [konfiguration.md](konfiguration.md) | Env-Variablen, Config-Optionen, Secrets-Handhabung |
| [datenmodell.md](datenmodell.md) | Schema, Migrationen, Datenverträge zwischen Komponenten |
| [api-referenz.md](api-referenz.md) | Endpunkte und öffentliche Schnittstellen |
| [sicherheit-datenschutz.md](sicherheit-datenschutz.md) | Secrets, personenbezogene Daten, externe Dienste, Audit |
| [bekannte-luecken.md](bekannte-luecken.md) | Abweichungen Spec ↔ Code, Stolpersteine, offene Bugs |
| [roadmap.md](roadmap.md) | Meilensteine und realistischer Umsetzungsstand |

## Pflegeregeln dieser Doku

- **Jede Information genau einmal.** Steht etwas in `AGENTS.md`, wird es hier nicht wiederholt,
  sondern verlinkt. Steht etwas in `architektur.md`, wird es in `api-referenz.md` verlinkt statt
  kopiert.
- Nicht zutreffende Dateien werden **gelöscht**, nicht mit Platzhaltertext stehengelassen.
  Ein leeres Gerüst ist schlimmer als eine fehlende Datei, weil ein Agent es für vollständig hält.
- Änderungen an Verhalten und Doku gehören ins **selbe** Arbeitspaket.
