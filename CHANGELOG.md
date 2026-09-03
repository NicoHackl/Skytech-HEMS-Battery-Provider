# Changelog

Alle nennenswerten Änderungen an Skytech HEMS Battery Provider.
Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

Kategorien: `Hinzugefügt`, `Geändert`, `Veraltet`, `Entfernt`, `Behoben`, `Sicherheit`.

Einträge werden aus **Nutzersicht** formuliert — was sich für den Anwender ändert, nicht welche
Datei angefasst wurde.

## [Unveröffentlicht]

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
- Soll-Ladeleistung und Soll-Entladeleistung lassen sich je Speicher setzen — **noch nicht an
  echter Hardware getestet**, vor dem ersten Einsatz mit kleinem Wert prüfen (siehe
  [docs/bekannte-luecken.md](docs/bekannte-luecken.md))
- Optionale HEMS-Anbindung: beim Einrichten eines Speichers lässt sich ein SkytechHEMS-Präfix
  hinterlegen (z. B. `acspeicher1`) — ab dann übersetzt die Integration die
  HEMS-Anforderungshelfer selbst laufend in Soll-Lade-/Entladeleistung, ohne dass dafür eine
  eigene Home-Assistant-Automation nötig ist. Leer lassen, wenn der Speicher nicht von
  SkytechHEMS gesteuert wird — **ebenfalls noch nicht an echter Hardware getestet**

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
