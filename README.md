# Git-Template

Vorlage für neue Projekte: Entwicklerrichtlinien, Designentscheidungen und KI-Agenten-Konfiguration
als Markdown — so verdrahtet, dass **jede Regel genau einmal existiert**.

> **Gerade erst in ein neues Repo kopiert?** Dann sag der KI einfach, worum es im Projekt geht.
> Sie findet die Regeln über [`AGENTS.md`](AGENTS.md) im Root von selbst und richtet das Repo ein
> — in Claude Code mit `/projekt-init`.
>
> **In ein bestehendes Projekt kopiert?** Dann `/projekt-pruefen`: Prüfung gegen alle Regeln und
> ein Migrationsplan, ohne dass eine Zeile Code angefasst wird. Details unten unter
> [Benutzung](#benutzung).

## Das Problem, das die Struktur löst

Claude Code liest `CLAUDE.md`, Codex liest `AGENTS.md`, GitHub Copilot liest
`.github/copilot-instructions.md`, Cursor liest `.cursor/rules/`, Gemini CLI liest `GEMINI.md`.
Fünf Dateien, fünf Tools — und wer sie inhaltlich pflegt, pflegt fünf Kopien, die
zwangsläufig auseinanderlaufen.

Hier gilt stattdessen: **`AGENTS.md` ist die einzige Quelle.** Alle anderen Tool-Dateien sind
Verweise darauf und enthalten selbst keine Regeln.

```text
                    ┌───────────────────────────┐
                    │        AGENTS.md          │  ← hier und nur hier
                    │  Regeln · Befehle · Index │     wird gepflegt
                    └─────────────┬─────────────┘
          ┌───────────────┬───────┴───────┬────────────────┐
          ▼               ▼               ▼                ▼
     CLAUDE.md       GEMINI.md    copilot-instr.md   .cursor/rules/
    (Claude Code)   (Gemini CLI)     (Copilot)          (Cursor)
     @AGENTS.md      @AGENTS.md       Verweis            Verweis
          │
          └─ verweist weiter auf ──►  docs/  (technische Tiefe, je Thema eine Datei)
```

## Drei Ebenen

| Ebene | Datei(en) | Inhalt |
|---|---|---|
| **Quelle** | `AGENTS.md` | Eiserne Regeln, Befehle, Arbeitsablauf, Verweistabelle auf `docs/` |
| **Tiefe** | `docs/*.md` | Architektur, Richtlinien, Entscheidungen, Tests, Security — je Thema eine Datei |
| **Adapter** | `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.cursor/rules/` | **nur Verweise**, kein Inhalt |

Regeln der Struktur:

- `AGENTS.md` enthält **keine** Architektur- oder API-Details — nur Verweise. Sonst driften Hub und
  `docs/` auseinander.
- `docs/*.md` wiederholt **keine** Regeln aus `AGENTS.md`.
- Präzedenz bei Widerspruch: **User-Anweisung > `AGENTS.md` > `docs/`**.

## Benutzung

### Weg 1: kopieren, Initialprompt, fertig (der normale Fall)

Inhalt dieses Repos in das neue Repo kopieren, KI starten, sagen worum es geht:

```text
> Das wird eine Home-Assistant-Integration für die Heizungssteuerung,
  Python 3.11 mit aiohttp, Tests mit pytest.
```

Ab da greift die Struktur von selbst: `AGENTS.md` liegt in der Wurzel, `CLAUDE.md`, `GEMINI.md`,
`.github/copilot-instructions.md` und `.cursor/rules/` zeigen darauf — jedes Werkzeug liest also
schon vor dem ersten Handgriff dieselben Regeln. Die Bootstrap-Fassung von `AGENTS.md` sagt der KI
außerdem, dass das Repo noch einzurichten ist, und wie:

1. Sie zieht Name, Zweck, Stack und Befehle aus dem Initialprompt.
2. Was fehlt, **fragt sie nach** — Weboberfläche ja/nein, Designsprache, Test- und Lint-Befehl.
3. Sie ruft `bin/init-projekt.sh --in-place …` auf: `vorlage/*` wandert in die Wurzel, Platzhalter
   werden gefüllt.
4. Das Gerüst räumt sich selbst weg — `vorlage/`, `frontend/`, `bin/` und der Bootstrap-Command
   sind danach verschwunden. Zurück bleibt nur das Projekt.

In Claude Code lässt sich Schritt 1–4 mit `/projekt-init` auch ausdrücklich anstoßen.

### Weg 2: bestehendes Projekt übernehmen

Auch das geht — nur nicht mit `cp -R`, das würde die `README.md` des Projekts überschreiben:

```bash
rsync -a --ignore-existing /pfad/zum/Git-Template/ ./     # oder: cp -Rn
```

Dann der KI sagen, sie soll das Projekt prüfen — in Claude Code `/projekt-pruefen`. Sie vergleicht
das Projekt Regel für Regel gegen `vorlage/AGENTS.md`, belegt jeden Befund mit `datei:zeile` und
schreibt einen `MIGRATION.md` mit Befundtabelle und einem Plan in drei Phasen: erst Regeln und Doku
ohne Codeänderung, dann mechanische Angleichung, zuletzt inhaltliche Umbauten — je Schritt Aufwand,
Risiko und Abhängigkeit, dazu ein Abschnitt „bewusst nicht angefasst".

**Geändert wird dabei nichts** außer dieser einen Datei. Welche Phase umgesetzt wird, entscheidest
du. Fehlende Vorlagendateien ergänzt danach `bin/init-projekt.sh --in-place --bestand …`, das
überschreibt nichts und listet auf, was von Hand zusammenzuführen ist.

### Weg 3: von außen in ein anderes Verzeichnis

```bash
bin/init-projekt.sh /pfad/zum/projekt \
    --name "Mein Projekt" \
    --zweck "Was das Projekt tut, in ein bis drei Sätzen." \
    --stack "Python 3.11, aiohttp, SQLite" \
    --install "uv sync" \
    --test "pytest" \
    --lint "ruff check ." \
    --build "docker compose up -d"
```

Vorher ansehen, was passieren würde:

```bash
bin/init-projekt.sh /pfad/zum/projekt --name "Mein Projekt" --dry-run
```

| Option | Wirkung |
|---|---|
| `--in-place` | Kein Zielpfad: dieses Repo selbst wird zum Projekt, `vorlage/*` wandert in die Wurzel, das Gerüst wird danach entfernt |
| `--bestand` | Bestandsprojekt: überschreibt **nichts**, ergänzt nur Fehlendes und listet auf, was von Hand zusammenzuführen ist. Das Gerüst bleibt stehen |
| `--design <ha\|fcr>` | Designsprache, Pflicht bei `--frontend`: `ha` (Home Assistant, Akzent `#18BCF2`) oder `fcr` (Vereinsfarben FC Ruderting). Kein Default |
| `--minimal` | Nur `AGENTS.md`, Adapter und die Kern-`docs/`-Dateien — für kleine Repos |
| `--frontend` | Referenz-SPA nach `web/` mitkopieren (siehe unten) |
| `--frontend-ordner <name>` | Wie `--frontend`, aber mit eigenem Zielordner (z. B. `admin_web`) |
| `--symlinks` | Adapter als Symlink auf `AGENTS.md` statt als Pointer-Datei |
| `--force` | Vorhandene Dateien überschreiben (Default: überspringen und melden) |
| `--dry-run` | Nur anzeigen, nichts schreiben |

Bestehende Dateien werden **nie** überschrieben, solange `--force` fehlt — das Skript ist damit
gefahrlos auf ein laufendes Projekt anwendbar. Nicht per Flag gesetzte Platzhalter bleiben als
`{{PLATZHALTER}}` stehen und werden am Ende aufgelistet.

## Pointer oder Symlink?

Default sind **Pointer-Dateien**: `CLAUDE.md` enthält nur `@AGENTS.md` (Claude-Import-Syntax),
`copilot-instructions.md` einen Verweissatz. Sichtbar im Dateibaum, funktioniert überall.

**Einschränkung:** Copilot lädt `copilot-instructions.md` zwar immer, folgt dem Verweis auf
`AGENTS.md` aber nur zuverlässig im Agent-Mode. Wer Copilot intensiv nutzt, nimmt `--symlinks`:
dann sind `CLAUDE.md`, `GEMINI.md` und `.github/copilot-instructions.md` echte Symlinks auf
`AGENTS.md`, jedes Tool sieht den vollen Inhalt. Git speichert Symlinks; auf Windows-Checkouts ohne
Symlink-Unterstützung bricht das.

## Inhalt der Vorlage

Vor der Einrichtung liegen in der Wurzel zusätzlich die Bootstrap-Dateien: `AGENTS.md` (Zustand +
Einrichtungsablauf), die vier Adapter darauf und `.claude/commands/projekt-init.md`. Sie werden bei
`--in-place` durch die Projektfassung ersetzt bzw. entfernt.

```text
vorlage/
├── AGENTS.md                      ← Quelle der Wahrheit
├── CLAUDE.md · GEMINI.md          ← Pointer
├── README.md · CONTRIBUTING.md · CHANGELOG.md
├── .cursor/rules/00-agents.mdc    ← Pointer (alwaysApply)
├── .claude/
│   ├── settings.json              ← geteilte Permissions (Secrets-Pfade gesperrt)
│   └── commands/                  ← /changelog · /adr · /doku-pruefen
├── .github/
│   ├── copilot-instructions.md    ← Pointer
│   ├── instructions/              ← pfadbezogene Regeln (Code, Tests, Frontend)
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── ISSUE_TEMPLATE/
└── docs/                          ← 16 Dateien: Architektur, Richtlinien, Frontend,
                                      Design-System, Nutzertexte, Git-Workflow, Tests,
                                      Entscheidungs-Log + ADR-Vorlage, Konfiguration,
                                      Datenmodell, API, Sicherheit, Lücken, Roadmap
```

## Frontend-Vorgabe

Für Web-Oberflächen ist der Stack **festgelegt**, übernommen aus `FCR_CMS` und
`FCR-Digitale-Stadion-Zeitung`: React 18 + TypeScript (`strict`) + Vite + `react-router-dom`,
eine einzige `styles.css` mit Design-Tokens, ein eigenes Icon-Set. Keine UI-Bibliothek, kein
CSS-Framework, kein State- oder Data-Fetching-Paket.

### Designsprachen — ein Vokabular, zwei Akzentsätze

Klassen, Abstände, Zustände und Icons sind identisch; unterschiedlich sind nur die fünf
Akzent-Tokens:

| Designsprache | Attribut | Akzent | Wofür |
|---|---|---|---|
| **Home Assistant** | `data-design="ha"` | `#18BCF2` | Projekte mit Bezug zu **Home Assistant** — weiße bzw. schwarze Basis je nach Modus |
| **FCR** | `data-design="fcr"` | `#8a1f33` hell / `#c2334c` dunkel | Projekte mit Bezug zum **FC Ruderting** |
| *keine* | fehlt | Grau aus der Textskala | Sichtbar unfertig — kein Zustand zum Ausliefern |

Gesetzt wird das beim Anlegen über `--design`; **einen Default gibt es nicht**, `--frontend` ohne
`--design` bricht ab. Gehört das Projekt zu keiner der beiden Welten oder ist die Zuordnung nicht
eindeutig, **fragt der Agent nach der Farbwahl, statt zu raten** — das ist eiserne Regel 10 in
`AGENTS.md`, nicht bloß eine Empfehlung. Eine dritte Designsprache ist eine dokumentierte
Design-Entscheidung, kein Nebenprodukt.

**Hell und Dunkel sind Pflicht**, in beiden Designsprachen: `data-theme` am `<html>`, Schalter in
der Kopfzeile jeder Seite, Voreinstellung vom Betriebssystem, Wahl in `localStorage`, und ein
Inline-Skript in `index.html` setzt den Modus vor dem ersten Frame — sonst blitzt Hell auf, bevor
React lädt.

Drei Dokumente machen das für Coding-KIs verbindlich, `AGENTS.md` verweist als eiserne Regel 8
bzw. 12 darauf:

| Datei | Inhalt |
|---|---|
| `docs/frontend.md` | Stack, Verzeichnisstruktur, Provider-Reihenfolge, Routing, API-Client, Formatierschicht, Listen- und Formularmuster, Hell/Dunkel-Mechanik, Auslieferung |
| `docs/design-system.md` | Designsprachen, Tokens je Modus (Farben, Radien, Schatten, Typo), vollständiger Klassenkatalog, Zustände, Haltepunkte, Icons, Barrierefreiheit |
| `docs/nutzertexte.md` | Was der Nutzer zu sehen bekommt: Zeit-, Zahlen- und Leerwertformate, Fehlermeldungen, Formulierung, Prüfliste |

`--frontend` legt zusätzlich die lauffähige Referenz-SPA an — das Design-System als Code, statt
es aus der Doku nachbauen zu lassen:

```text
frontend/                     ← nur mit --frontend, landet als web/ im Projekt
├── index.html · vite.config.ts · tsconfig*.json · package.json · nginx.conf
└── src/
    ├── styles.css            ← das gesamte Design-System, Tokens oben (hell + dunkel)
    ├── main.tsx · App.tsx    ← Provider-Verdrahtung, reine Routentabelle
    ├── api.ts · types.ts     ← einziger fetch-Ort, ApiError, Datenverträge
    ├── format.ts             ← Rohwert → Anzeigetext (Datum, Uhrzeit, Zahl, Leerwert)
    ├── components/           ← Layout + PageHeader, Theme, Toast, Icon
    └── pages/                ← Dashboard und Liste als Muster zum Ersetzen
```

Danach `cd web && npm install && npm run dev`. Anzupassen sind — falls eine eigene Akzentfarbe
nötig ist — die fünf `--primary`-Tokens je Modus in `src/styles.css`, die Ports in
`vite.config.ts` und die Beispielseiten.

## Nach dem Anlegen

1. `AGENTS.md` ausfüllen — Zweck, Befehle, projekteigene Regeln.
2. Nicht zutreffende `docs/`-Dateien **löschen** und aus `docs/README.md` austragen.
   Ein leeres Gerüst ist schlimmer als eine fehlende Datei: ein Agent hält es für vollständig.
3. `.gitignore` ergänzen (`.env`, `.venv`, `node_modules`, `dist`).
4. Regeln ab jetzt **nur** in `AGENTS.md` ändern.

## Mitgelieferte Slash-Commands

Nach dem Kopieren in Claude Code verfügbar:

| Befehl | Wirkung |
|---|---|
| `/changelog` | Erzeugt Changelog-Einträge aus dem aktuellen Diff, nach Nutzersicht formuliert |
| `/adr` | Legt eine Design-Entscheidung im Log an, bei Tragweite zusätzlich als ADR |
| `/doku-pruefen` | Gleicht `docs/` gegen den echten Code ab und meldet Abweichungen |
