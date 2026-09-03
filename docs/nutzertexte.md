# Nutzertexte — was der Nutzer zu sehen bekommt

> Gilt für **jede** Ausgabe an einen Menschen: Config-Flow-Dialoge, Entity-Namen, Log-Meldungen,
> Fehlermeldungen. Dieses Projekt hat keine eigene Oberfläche (eiserne Regel 8) — „Oberfläche"
> meint hier ausschließlich die Home-Assistant-Standard-UI (Lovelace, Config-Flow, Toasts). Es
> gibt deshalb kein `design-system.md`/`frontend.md` in diesem Repo — hier steht, was die
> HA-Oberfläche **sagt**.

## Grundsatz

Eine Vorgabe an die Umsetzung ist **kein Anzeigetext**. Dass Uhrzeiten in Berliner Zeit gerechnet
werden, ist eine Umrechnungsvorschrift — der Nutzer liest `21:03`, nicht `21:03 Berliner Zeit`.
Dasselbe gilt für jede andere Festlegung: Datenformat, Einheit, Zeichensatz, Statuscode,
Schlüsselschema. Der Nutzer sieht das **Ergebnis**, nie die Regel, nach der es entstanden ist.

Prüffragen vor jedem Text, der auf den Bildschirm geht:

1. **Beantwortet die Angabe eine Frage, die der Nutzer hat?** Nein → weglassen.
2. **Kann er wegen dieser Angabe etwas anderes tun?** Nein → weglassen.
3. **Wüsste er es ohnehin, weil es immer so ist?** Ja → weglassen.

Was dabei wegfällt, verschwindet nicht, sondern wandert ins Log — siehe
[entwicklerrichtlinien.md](entwicklerrichtlinien.md).

## Wer liest das?

Die Regel ist keine Aufforderung, Ausgaben pauschal zu verarmen. Sie richtet sich nach dem
Publikum:

| Publikum | Beispiel | Detailtiefe |
|---|---|---|
| **Endnutzer** | Oberfläche, Toast, E-Mail, App | Nur, was seine Frage beantwortet. Kein Technikwort. |
| **Betreiber** | Startabbruch, Konfigurationsfehler, `--help`, Admin-CLI | Pfad, Variablenname und erwarteter Wert **gehören dazu** — er soll es ja reparieren. |
| **Entwickler** | Log, Stacktrace, Debug-Ausgabe | Vollständig, ungekürzt, technisch. |

Ein Konfigurationsfehler beim Start ist also weiterhin `Umgebungsvariable API_TOKEN fehlt —
erwartet in .env` (siehe [konfiguration.md](konfiguration.md)) und nicht „Es ist ein Fehler
aufgetreten". Falsch wäre nur, dieselbe Meldung dem Endnutzer in der Oberfläche zu zeigen.

## Was nie in der Oberfläche steht

| Statt dessen sichtbar | Richtig | Wohin es gehört |
|---|---|---|
| `21:03 Berliner Zeit`, `21:03 (Europe/Berlin)`, `21:03 MESZ`, `+02:00` | `21:03` | nirgends — die Zone ist Rechenvorschrift, eiserne Regel 9 |
| `2026-08-15T19:03:22.417Z` | `15.08.2026, 21:03` | Maschinenformat bleibt in API und Datenbank |
| `Anfrage fehlgeschlagen (500)`, `HTTP 404`, `ApiError` | „Die Einträge konnten nicht geladen werden. Bitte später erneut versuchen." | Statuscode und Klassenname ins Log |
| `Eintrag #4711 gelöscht` | „„Sommerfest" wurde gelöscht." | ID ins Log |
| `Status: PENDING_SYNC` | „Wird übertragen" | Enum-Wert bleibt im Code |
| `Feld title darf nicht leer sein` | „Titel darf nicht leer sein" (am Feld, nicht als Toast) | Feldname bleibt im Vertrag |
| `/var/lib/app/data.db`, `SELECT * FROM …`, Stacktrace | „Die Daten sind gerade nicht erreichbar." | vollständig ins Log |
| `Fehler in fetch()`, „React-Fehler", „Vite-Build" | „Speichern hat nicht geklappt." | Werkzeugnamen sagen dem Nutzer nichts |
| `null`, `undefined`, `N/A`, `-1` | `–` oder ein Satz, der erklärt, warum nichts da ist | technische Leerwerte nie durchreichen |
| `21.000000001 kWh` | `21,0 kWh` | Rohwert bleibt in den Daten |
| Hinweise, die immer gelten: „(in Sekunden)", „Format TT.MM.JJJJ", „(deutsch)" | die Einheit am Wert (`30 s`), das Format im Eingabefeld selbst | — |

Die Liste ist nicht abschließend. Sie zeigt das Muster: **alles, was aus einer technischen
Festlegung stammt und keine Handlung des Nutzers ändert, wird nicht angezeigt.**

## Zeitangaben

- Uhrzeit `hh:mm`, Datum `TT.MM.JJJJ`, zusammen `15.08.2026, 21:03` — Format und Zone regelt
  eiserne Regel 9 in [`../AGENTS.md`](../AGENTS.md), hier steht nur, **wie viel** davon zu sehen ist.
- **Nur so genau wie nötig.** Sekunden erscheinen nur, wo sie eine Entscheidung ändern (Protokolle,
  Messreihen). „Zuletzt geändert" braucht keine Sekunden.
- **Nur so viel wie nötig.** Ist alles vom selben Tag, reicht die Uhrzeit; ist alles vom selben
  Jahr, reicht `TT.MM.`. Ein wiederholtes Jahr in jeder Tabellenzeile ist Rauschen.
- Relative Angaben („vor 5 Minuten") sind zulässig, aber **eine** Entscheidung fürs ganze Projekt —
  nicht mal so, mal anders. Beschluss nach
  [design-entscheidungen.md](design-entscheidungen.md).
- Es gibt in diesem Repo keine eigene Formatierschicht wie in einem Frontend üblich — Einheiten,
  Nachkommastellen und Zeitformate kommen aus den Standardattributen der HA-Entities
  (`native_unit_of_measurement`, `device_class`, `suggested_display_precision`); die Anzeige
  übernimmt Home Assistant selbst.
- **Ausnahme, in der die Zone doch dazugehört:** Daten aus mehreren Zeitzonen, zwischen denen der
  Nutzer unterscheiden muss (Reise, internationale Termine). Das ist ein Sonderfall, der
  ausdrücklich entschieden wird — nicht der Normalfall, und nie ein pauschaler Zusatz.

## Zahlen, Mengen, Einheiten

- Deutsche Schreibweise: Komma als Dezimaltrenner, Punkt als Tausendertrenner (`1.234,5`).
- Einheit mit schmalem Abstand am Wert (`30 s`, `21,0 kWh`, `12 °C`), nicht im Label wiederholt.
- **Nie mehr Nachkommastellen anzeigen, als die Quelle hergibt.** Ein Sensor mit 0,5 °C Auflösung
  zeigt `21,5 °C`, nicht `21,4999998 °C` — angezeigte Genauigkeit ist ein Versprechen.
- Zählungen ohne Ergebnis zeigen `–`, nicht `0`, wenn nicht sicher ist, dass wirklich null gemeint
  ist. Ein fehlgeschlagener Abruf ist kein Nullwert.

## Fehlermeldungen

Drei Teile, in dieser Reihenfolge, in einem oder zwei Sätzen:

1. **Was nicht geklappt hat** — aus Nutzersicht, nicht aus Systemsicht.
2. **Was das für ihn bedeutet** — nur, wenn es nicht offensichtlich ist.
3. **Was er tun kann** — der wichtigste Teil, und der, der am häufigsten fehlt.

| Schlecht | Gut |
|---|---|
| „Fehler aufgetreten." | „Der Eintrag konnte nicht gespeichert werden. Bitte erneut versuchen." |
| „Anfrage fehlgeschlagen (422)." | „Bitte Titel ausfüllen." — direkt am Feld |
| „Verbindung zu 10.0.0.4:8080 abgelehnt." | „Der Server ist gerade nicht erreichbar." |
| „Ungültiger Wert in Feld `starts_at`." | „Das Startdatum liegt in der Vergangenheit." |

Gleichzeitig gilt: **Die technische Ursache geht nicht verloren.** Sie wird geloggt, bevor die
verständliche Meldung entsteht. Eine Meldung, die dem Nutzer nichts sagt *und* im Log fehlt, ist
zweimal wertlos.

## Wenn technische Angaben doch gebraucht werden

Es gibt sie — Support-Fälle, Administrationsbereiche, Entwicklerwerkzeuge. Dann gilt:

- Das Technische ist **aufklappbar oder auf einer eigenen Seite**, nie in der Hauptzeile.
  `<details>`-Karte (`.advanced-card`), „Details anzeigen", Admin-Ansicht.
- Für den Support genügt **eine** kopierbare Kennung („Fehlernummer `7f3a`"), nicht der Stacktrace.
- Ein Administrationsbereich ist keine Ausrede für Rohdaten: auch dort wird formatiert, nur mit
  mehr Detailtiefe.
- Manches darf aus **Sicherheitsgründen** ohnehin nicht sichtbar sein — Pfade, Hostnamen,
  Versionsnummern, die Existenz eines Kontos. Siehe
  [sicherheit-datenschutz.md](sicherheit-datenschutz.md).

## Formulierung

- Deutsch, ganze Sätze mit Punkt, aktiv statt passiv. „Der Eintrag wurde gelöscht." statt
  „Löschvorgang erfolgreich."
- Anrede (`du` oder `Sie`) ist projektweit **eine** Festlegung. Ist sie nicht getroffen, wird
  gefragt und das Ergebnis in [design-entscheidungen.md](design-entscheidungen.md) eingetragen —
  gemischte Anrede in einer Oberfläche fällt sofort auf.
- Buttons benennen die Handlung, nicht das System: „Eintrag anlegen", nicht „Absenden", nicht „OK".
- Keine Entschuldigungen und keine Ausrufezeichen. „Leider ist ein Fehler aufgetreten!" hilft
  niemandem.
- Fachbegriffe der **Domäne** sind erlaubt und erwünscht (der Nutzer kennt sie), Fachbegriffe der
  **Technik** nicht (er kennt sie nicht und braucht sie nicht).

## Checkliste vor dem Commit

1. Keine Zeitzone, kein Offset, kein Zonenkürzel in einem sichtbaren Text.
2. Kein Statuscode, kein Klassenname, kein Stacktrace, kein Dateipfad in einer Meldung.
3. Keine technische ID sichtbar, wo ein Name verfügbar ist.
4. Kein `null`, `undefined` oder `NaN` im Markup — Leerwerte werden abgefangen.
5. Jede Fehlermeldung sagt, was der Nutzer tun kann.
6. Jeder Rohwert aus der API läuft durch eine Formatierfunktion, bevor er gerendert wird.
7. Einmal die fertige Seite lesen und bei jeder Angabe fragen: *Interessiert das den Nutzer?*
