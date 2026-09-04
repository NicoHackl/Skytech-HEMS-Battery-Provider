# Changelog

Alle nennenswerten Änderungen an Skytech HEMS Battery Provider.
Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

Kategorien: `Hinzugefügt`, `Geändert`, `Veraltet`, `Entfernt`, `Behoben`, `Sicherheit`.

Einträge werden aus **Nutzersicht** formuliert — was sich für den Anwender ändert, nicht welche
Datei angefasst wurde.

## Unveröffentlicht

### Hinzugefügt

- Lizenz festgelegt: MIT.

## [0.4.0] — 04.09.2026

### Hinzugefügt

- Neuer Schalter je Speicher mit aktiver HEMS-Anbindung: „HEMS-Steuerung" pausiert/setzt die
  automatischen Schreibvorgänge der HEMS-Anbindung fort. Ausgeschaltet lassen sich
  Soll-Ladeleistung und Soll-Entladeleistung wieder von Hand setzen, ohne dass der nächste
  HEMS-Zyklus sie sofort überschreibt. Eingeschaltet übernimmt die HEMS-Anbindung sofort wieder
  den aktuellen Sollwert, statt erst auf die nächste Änderung der HEMS-Vorgabe zu warten. Der
  Schalter steht nach jedem Neustart von Home Assistant oder Neuladen der Integration wieder auf
  EIN — eine Pause übersteht das bewusst nicht. Nur sichtbar, wenn für den Speicher ein
  SkytechHEMS-Präfix eingerichtet ist.

## [0.3.0] — 04.09.2026

### Geändert

- Der in Home Assistant und HACS angezeigte Name lautet jetzt „Skytech HEMS Battery Provider"
  statt „Battery Bridge" — nur der Anzeigename ändert sich, bestehende Speicher, Entities und
  Einstellungen bleiben unverändert erhalten.

### Hinzugefügt

- Zwei neue Sensoren je Speicher mit aktiver HEMS-Anbindung: HEMS-Soll-Ladeleistung und
  HEMS-Soll-Entladeleistung zeigen den Sollwert, den die Integration zuletzt tatsächlich an den
  Speicher gesendet hat. Bisher ließ sich das nirgends ablesen, weil die HEMS-Anbindung direkt am
  Adapter vorbei schreibt, ohne die bestehenden Soll-Leistungs-Entities zu berühren — siehe
  [docs/bekannte-luecken.md](docs/bekannte-luecken.md). Nur sichtbar, wenn für den Speicher ein
  SkytechHEMS-Präfix eingerichtet ist.

## [0.2.1] — 03.09.2026

### Behoben

- Speicher „sprang" ständig auf 0 W und wieder zurück, solange die HEMS-Anbindung aktiv war —
  jede Anpassung der Soll-Leistung hat die inaktive Richtung unnötig auf 0 gesetzt, bevor die
  eigentlich gewünschte Richtung geschrieben wurde. Beide Befehle landen bei diesem Speicher auf
  demselben Gerätewert, dadurch kam der Zwischenschritt am Gerät als kurzer Sprung an. Die
  inaktive Richtung wird jetzt nur noch beim tatsächlichen Wechsel zwischen Laden/Entladen/
  Standby einmal zurückgesetzt.
- Ist-Ladeleistung/Ist-Entladeleistung zeigten auf manchen Anlagen dauerhaft „nicht verfügbar",
  weil der Speicher den erwarteten Leistungswert nicht mitliefert. Die Integration weicht in
  diesem Fall auf einen Ersatzwert aus einem anderen, vom Speicher gelieferten Feld aus — siehe
  [docs/bekannte-luecken.md](docs/bekannte-luecken.md) für Details und Einschränkungen.

## [0.2.0] — 03.09.2026

### Hinzugefügt

- Projektgerüst mit Doku- und Agentenstruktur angelegt
- Projektdoku (`docs/`) mit der konkreten Architektur aus `plan.md` gefüllt: Komponenten,
  Verzeichnisstruktur, Entities, Adapter-Vertrag, offene Fragen vor der Marstek-Implementierung

- Batteriespeicher lassen sich über **Einstellungen → Geräte & Dienste → Integration hinzufügen**
  einrichten: Hersteller Marstek wählen, IP-Adresse und Port eingeben, Verbindung wird vor dem
  Anlegen getestet
- Drei Sensoren je eingerichtetem Speicher: Ladezustand, Ist-Ladeleistung, Ist-Entladeleistung —
  aktualisieren sich automatisch alle 5 Sekunden, zeigen „nicht verfügbar", wenn der Speicher
  gerade nicht antwortet
- Soll-Ladeleistung und Soll-Entladeleistung lassen sich je Speicher setzen
- Optionale HEMS-Anbindung: beim Einrichten eines Speichers lässt sich ein SkytechHEMS-Präfix
  hinterlegen (z. B. `acspeicher1`) — ab dann übersetzt die Integration die
  HEMS-Anforderungshelfer selbst laufend in Soll-Lade-/Entladeleistung, ohne dass dafür eine
  eigene Home-Assistant-Automation nötig ist. Leer lassen, wenn der Speicher nicht von
  SkytechHEMS gesteuert wird

  Erster Praxistest an einer echten Venus E 3.0: Ladezustand liest korrekt, Ist-Ladeleistung/
  Ist-Entladeleistung zeigen noch `unknown` (Ursache offen), siehe
  [docs/bekannte-luecken.md](docs/bekannte-luecken.md)

### Geändert

- Frontend-Vorlage entfernt — diese Integration hat keine eigene Web-Oberfläche, Entities laufen
  über die Home-Assistant-Standard-UI

### Behoben

- Schlug das Setzen einer Soll-Lade-/Entladeleistung fehl, zeigte die Meldung bisher technische
  Details (Geräteadresse, interne Protokoll-Angaben). Jetzt ein verständlicher, allgemeiner
  Hinweis; die technischen Details stehen weiterhin vollständig im Log.
- Setzte die HEMS-Anbindung (oder ein manuelles Setzen der Soll-Lade-/Entladeleistung) fast
  immer den Sollwert nicht am Speicher, weil sich ein laufender Lesevorgang (alle 5 Sekunden)
  und ein gleichzeitiger Schreibvorgang der HEMS-Anbindung gegenseitig die Geräteantwort
  wegschnappen konnten — beide teilten sich dieselbe Warteschlange ohne Absicherung. Anfragen
  an den Speicher laufen jetzt nacheinander ab, nie mehr gleichzeitig.

## [0.1.0] — 02.09.2026

### Hinzugefügt

- Erste Version
