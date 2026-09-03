# Sicherheit und Datenschutz

## Zugangsdaten

- Keine Secrets im Code, in Logs, in Pfaden oder in Commit-Messages — siehe
  [`AGENTS.md`](../AGENTS.md), Regel 6. Handhabung: [konfiguration.md](konfiguration.md).
- Vor jedem Commit `git diff --staged` prüfen.
- Ein versehentlich gepushtes Secret gilt als kompromittiert: **rotieren**, nicht nur aus der
  Historie entfernen. Ein `git rebase` macht das Leak nicht ungeschehen.

## Eingaben

- Jede Eingabe von außen (User, API, Datei, Netzwerk) wird validiert, bevor sie verwendet wird.
- Bezeichner, die in Dateipfade einfließen, werden gegen eine Allowlist geprüft (nur Buchstaben,
  Zahlen, Punkt, Unterstrich, Bindestrich) — sonst Directory-Traversal.
- Datenbankzugriffe ausschließlich parametrisiert, nie per String-Verkettung.
- Ausgaben in HTML werden escaped.

## Ausgaben

Was der Nutzer nicht zu sehen braucht, ist nicht nur Rauschen, sondern eine Auskunft über das
System — Regel 12 hat damit auch eine Sicherheitsseite:

- Fehlermeldungen nennen **nie** Pfade, Hostnamen, Ports, Versionsnummern, Stacktraces,
  SQL-Fragmente oder Namen interner Dienste. Das alles geht ins Log, nicht auf den Bildschirm.
- Anmeldung und Passwortzurücksetzung antworten **gleich**, egal ob das Konto existiert
  („Wenn ein Konto existiert, wurde eine E-Mail versendet."). Unterschiedliche Meldungen sind eine
  Kontoliste zum Abfragen.
- Fehlende Berechtigung wird nicht mit dem Detail begründet, das sie verrät („nur für Admins der
  Gruppe X") — ein sachlicher Satz genügt.
- Für Support-Fälle eine kurze Kennung ausgeben, die im Log denselben Vorgang findet; der Nutzer
  bekommt die Nummer, nicht den Inhalt.

Formulierung und Format der sichtbaren Texte: [nutzertexte.md](nutzertexte.md).

## Personenbezogene Daten

| Datenart | Wird verarbeitet? | Wo gespeichert | Löschfrist |
|---|---|---|---|
| Personenbezogene Daten jeder Art | nein | — | — |

Verarbeitet werden ausschließlich Gerätemesswerte (SoC, Leistung) und Verbindungsdaten
(Host/IP, Port) eines im eigenen LAN stehenden Speichers. Grundsatz Datenminimierung: Was nicht
erhoben wird, kann nicht verloren gehen.

## Externe Dienste

| Dienst | Welche Daten gehen dorthin | Warum nötig |
|---|---|---|
| Keine — Marstek Local API läuft rein im LAN, kein Cloud-Zugriff auf Herstellerserver (Nicht-Ziel, siehe [architektur.md](architektur.md)) | — | — |

Ein neuer externer Dienst (z. B. eine künftige Cloud-API als Adapter) ist eine
Design-Entscheidung → Eintrag in [design-entscheidungen.md](design-entscheidungen.md), inklusive
der Frage, welche Daten das Haus verlassen.

## Abhängigkeiten

- Sicherheitsupdates zeitnah einspielen.
- Neue Abhängigkeiten vor Aufnahme prüfen: Wartungsstand, Verbreitung, Lizenz.

## Grenzen für KI-Agenten

- Kein von einer KI erzeugter Code wird ungeprüft ausgeführt.
- Freitext einer KI ist nie ein Steuerbefehl — nur strukturierte, validierte Ein- und Ausgaben.
- An externe KI-Dienste gehen nur die für die Aufgabe nötigen, verdichteten Daten — nie ganze
  Datenbanken, nie personenbezogene Daten ohne ausdrückliche Freigabe.
- Harte Sicherheitsgrenzen sind durch eine KI nicht änderbar.
