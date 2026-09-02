# Teststrategie

## Befehle

```bash
{{TEST_BEFEHL}}              # alle Tests
{{TEST_BEFEHL}} <pfad>       # gezielt eine Datei
{{LINT_BEFEHL}}              # Linting und Formatprüfung
```

Beides muss vor jedem Commit fehlerfrei durchlaufen — siehe [git-workflow.md](git-workflow.md).

## Testarten

| Art | Umfang | Ort |
|---|---|---|
| Unit | Eine Funktion oder Klasse, keine externen Zugriffe | `tests/unit/` |
| Integration | Zusammenspiel mehrerer Komponenten, echtes Schema | `tests/integration/` |
| Regression | Ein konkret aufgetretener Bug, damit er nicht wiederkehrt | beim jeweiligen Modul |

Die Teststruktur spiegelt die Struktur des Quellcodes. Zu `{{QUELLCODE_ORDNER}}/planer/rechner.*`
gehört `tests/unit/planer/test_rechner.*`.

## Pflicht-Testfälle

Für jede neue Funktion mindestens:

1. **Normalfall** — erwartete Eingabe, erwartetes Ergebnis
2. **Fehlerfall** — ungültige Eingabe, definierter Fehler statt Absturz
3. **Leerzustand** — leere Liste, `null`, fehlende Datei

Für Funktionen, deren Ergebnis ein Mensch liest (Formatierung, Meldungstexte), zusätzlich:

4. **Anzeigeform** — das Ergebnis entspricht dem Format aus
   [nutzertexte.md](nutzertexte.md): `15.08.2026`, `21:03`, `1.234,5` — **ohne** Zonenkürzel,
   Offset, Statuscode oder technische Kennung. Zeitfunktionen werden dabei mit einem festen
   Zeitpunkt geprüft, je einmal in Sommer- und Winterzeit, damit die Umrechnung nachweislich
   stimmt, ohne dass die Zone im Text auftaucht.
5. **Leerwert** — `null`, `undefined` und ein unbrauchbarer Wert ergeben den Platzhalter, nie
   `null`, `undefined` oder `NaN` als Text.

Ein Bugfix ohne Regressionstest ist nicht abgeschlossen. Der Test muss **vor** dem Fix
nachweislich fehlschlagen.

## Grundregeln

- Tests laufen **ohne** Netzwerkzugriff, ohne echte Zugangsdaten und ohne spezielle Hardware.
  Externe Dienste werden gemockt.
- Tests sind reihenfolgeunabhängig und hinterlassen keinen Zustand.
- Keine `sleep`-Aufrufe zur Synchronisierung — sie sind langsam und trotzdem instabil.
- Ein Test prüft **eine** Aussage. Der Testname beschreibt sie:
  `test_berechnet_null_bei_leerer_geraeteliste`.
- Testdaten liegen als Fixture vor und werden nicht von Hand editiert, wenn sie generiert werden.

## Coverage

Zielwert: **{{COVERAGE_ZIEL}}**. Coverage ist ein Warnsignal, kein Ziel an sich — 100 % Coverage
ohne Zusicherungen im Test ist wertlos. Ungetestet bleiben dürfen generierte Dateien und triviale
Getter.

## Fixtures

<Wie Testdaten entstehen. Falls generiert, hier der Befehl:>

```bash
<generator-befehl>
```

Generierte Fixtures werden nie von Hand bearbeitet — sonst weicht der Test vom echten Schema ab.
