# AGENTS.md — noch nicht eingerichtetes Projekt

> **Diese Datei ist eine Bootstrap-Fassung.** Sie wird bei der Initialisierung durch die
> Projektfassung aus `vorlage/AGENTS.md` ersetzt und verschwindet damit von selbst.

## Zustand erkennen

| Was du siehst | Was das heißt | Was zu tun ist |
|---|---|---|
| `vorlage/` und `bin/` existieren, sonst nur Template-Dateien | Frisch kopiertes Template, **leeres Projekt** | [Initialisierung](#initialisierung--die-erste-aufgabe-vor-jeder-anderen) |
| `vorlage/` existiert **und** daneben liegt schon Projektcode | Die Vorlage wurde in ein **Bestandsprojekt** kopiert | [Bestandsprojekt übernehmen](#bestandsprojekt-übernehmen) |
| `vorlage/` und `bin/` fehlen, `AGENTS.md` nennt einen Projektnamen | Eingerichtet — diese Datei liest du dann gar nicht mehr | nichts |

Projektcode erkennst du an dem, was das Template nicht mitbringt: Quellordner, `package.json`,
`pyproject.toml`, `src/`, eine Git-Historie mit fremden Commits.

## Die Regeln gelten ab sofort

Die verbindlichen Regeln stehen in [`vorlage/AGENTS.md`](vorlage/AGENTS.md) und gelten **schon
vor** der Initialisierung — auch für dieses erste Gespräch. Sie werden hier bewusst nicht
wiederholt: jede Regel existiert genau einmal. Lies die Datei, bevor du irgendetwas tust.

Was daraus sofort greift, noch bevor eine Zeile Code entsteht:

- **Nicht raten.** Unklare Anforderung → fragen. Getroffene Annahmen ausdrücklich nennen.
- **Datum und Uhrzeit** immer `TT.MM.JJJJ` und Berliner Zeit ohne Offset (eiserne Regel 9) — die
  Zone wird gerechnet, nicht geschrieben: `21:03`, nie „21:03 Berliner Zeit".
- **Nur zeigen, was den Nutzer betrifft** (eiserne Regel 12): keine Statuscodes, IDs, Stacktraces,
  Pfade oder internen Zustandsnamen in sichtbaren Texten. Technisches gehört ins Log.
- **Designsprache** wird nie geraten (eiserne Regel 10): `fcr` für FC Ruderting, `ha` für
  Home Assistant, **jedes andere Projekt und jeder Zweifelsfall → nachfragen**.
- **Sprache:** Code englisch, Kommentare und alle Texte für Menschen deutsch.

## Initialisierung — die erste Aufgabe, vor jeder anderen

In Claude Code genügt `/projekt-init`. Jedes andere Werkzeug arbeitet diese Schritte direkt ab:

1. [`vorlage/AGENTS.md`](vorlage/AGENTS.md) lesen, dazu [`README.md`](README.md) für den Aufbau.
2. Aus dem Initialprompt des Users herausziehen, was er hergibt:

   | Angabe | Flag | Beispiel |
   |---|---|---|
   | Projektname | `--name` | `"Heizungssteuerung"` |
   | Zweck, 1–3 Sätze | `--zweck` | `"Steuert die Heizkreise über Home Assistant."` |
   | Tech-Stack | `--stack` | `"Python 3.11, aiohttp, SQLite"` |
   | Installieren | `--install` | `"uv sync"` |
   | Tests | `--test` | `"pytest"` |
   | Linting | `--lint` | `"ruff check ."` |
   | Build | `--build` | `"docker compose up -d"` |
   | Arbeitsbranch | `--branch` | Default `agent/main` |
   | Web-Oberfläche? | `--frontend` | legt die Referenz-SPA unter `web/` an |
   | Designsprache | `--design` | `ha` oder `fcr` — **Pflicht**, sobald `--frontend` |

3. **Was nicht zweifelsfrei aus dem Prompt hervorgeht, wird gefragt — gesammelt in einer
   Rückfrage, nicht in sieben.** Besonders: Braucht das Projekt eine Weboberfläche? Und wenn ja,
   welche Designsprache, falls es weder FC Ruderting noch Home Assistant ist?
4. Einrichten:

   ```sh
   bin/init-projekt.sh --in-place \
       --name "…" --zweck "…" --stack "…" \
       --install "…" --test "…" --lint "…" --build "…" \
       [--frontend --design ha|fcr] [--minimal]
   ```

   `--in-place` rollt `vorlage/*` in die Wurzel aus, füllt die Platzhalter und entfernt
   anschließend das Gerüst: `vorlage/`, `frontend/`, `bin/` und den Bootstrap-Command.
5. Ergebnis prüfen: `AGENTS.md` in der Wurzel nennt den Projektnamen, `vorlage/`, `frontend/`
   und `bin/` sind weg. Ist etwas davon übrig, von Hand entfernen.
6. Die vom Skript gemeldeten offenen Platzhalter (`{{…}}`) mit dem User klären und eintragen —
   ein stehengebliebener Platzhalter in einer Agenten-Anweisung ist eine Anweisung ins Leere.
7. `.gitignore` ergänzen (`.env`, `.venv`, `node_modules`, `dist`), ersten Commit auf dem
   Arbeitsbranch anlegen.
8. **Erst danach** mit der eigentlichen Aufgabe aus dem Initialprompt beginnen.

Nicht zutreffende `docs/`-Dateien werden gelöscht und aus `docs/README.md` ausgetragen. Ein leeres
Gerüst ist schlimmer als eine fehlende Datei: der nächste Agent hält es für vollständig.

## Bestandsprojekt übernehmen

Liegt neben `vorlage/` bereits Projektcode, wird **nicht** initialisiert. Ein Bestandsprojekt wird
erst geprüft, dann geplant, dann migriert — in dieser Reihenfolge und nie in einem Rutsch.

In Claude Code: `/projekt-pruefen`. Jedes andere Werkzeug arbeitet dasselbe ab:

1. [`vorlage/AGENTS.md`](vorlage/AGENTS.md) lesen — die eisernen Regeln sind der Maßstab.
2. Das Projekt gegen jede Regel prüfen und jeden Befund mit `datei:zeile` belegen. Bewertung je
   Regel: erfüllt / teilweise / verletzt / nicht anwendbar. Was das Projekt nicht hat, wird nicht
   geprüft — „nicht anwendbar" ist ein Ergebnis, kein Ausweichen.
3. Ergebnis als `MIGRATION.md` in die Wurzel schreiben: Befundtabelle, dann ein Plan in drei
   Phasen — erst Regeln und Doku ohne Codeänderung, dann mechanische Angleichung, zuletzt
   inhaltliche Umbauten. Je Schritt Aufwand, Risiko und Abhängigkeit. Dazu ein Abschnitt „bewusst
   nicht angefasst" mit Begründung.
4. **Dabei wird nichts geändert** außer `MIGRATION.md` selbst. Der Plan geht an den User; welche
   Phase umgesetzt wird, entscheidet er.
5. Ist die Designsprache nicht zweifelsfrei ableitbar, wird gefragt — auch im Plan wird sie nicht
   geraten (eiserne Regel 10).
6. Fehlende Vorlagendateien ergänzt danach:

   ```sh
   bin/init-projekt.sh --in-place --bestand --name "…" --zweck "…" --stack "…"
   ```

   `--bestand` überschreibt **nichts** — es legt nur an, was fehlt, und listet auf, welche Dateien
   von Hand zusammenzuführen sind. Das Gerüst bleibt dabei stehen, bis das erledigt ist; erst dann
   `vorlage/`, `frontend/`, `bin/` und die Bootstrap-Commands entfernen.

**Beim Kopieren in ein Bestandsprojekt** nichts überschreiben — sonst ist die `README.md` des
Projekts weg, bevor die Prüfung beginnt:

```sh
rsync -a --ignore-existing /pfad/zum/Git-Template/ ./     # oder: cp -Rn
```
