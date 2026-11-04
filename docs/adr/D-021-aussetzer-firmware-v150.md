# D-021: Aussetzer seit Firmware V150 überbrücken und den Sollwert danach sofort erneuern

- **Datum:** 04.11.2026
- **Status:** Aktiv, Wirkung an Hardware noch nicht gemessen
- **Betrifft:** `adapters/marstek_udp.py`, `adapters/base.py`, `adapters/e3dc_rscp.py`, `const.py`,
  `coordinator.py`, `hems_bridge.py`, `models.py`, HEMS-Vertrag (Abschnitt Keep-Alive)

## Kontext

Seit dem 03.11.2026 gegen 17:00, zeitlich passend zum Update der Venus E 3.0 auf Firmware V150,
antwortet das Gerät mehrmals pro Stunde nicht mehr über die Local API. Ausgewertet am 04.11.2026:

- 37 Ausfälle in 132 min nach dem Stromlos-Schalten um 11:32, zwei Klassen:
  - 13 kurz (unter 8 s): das Gerät antwortet nach wenigen Sekunden wieder. Die Ladepause entsteht
    erst, weil die Entitäten `unavailable` werden und das HEMS auf Standby geht.
  - 24 lang (ab 8 s): 0 W nach rund 10 s, 23-mal danach rund -150 W nach rund 23 s, Daten erst nach
    30–63 s zurück.
- Ohne API-Verkehr traten in 45 min keine Ereignisse auf. Mit Lesen allein traten sie auf.
- Im Standby gab der Speicher rund 154 W ab, obwohl 0 W angefordert waren. Das endete zeitlich mit
  dem nächsten Keep-Alive, nicht schon mit der ersten Antwort (13:56:20 Antwort, 13:57:04 Ende).
- Eine [Community-Analyse](https://raw.githubusercontent.com/sphings79/marstek-modbus-suite/main/FIRMWARE-DROPOUTS.md)
  beschreibt für V150 einen rund 4 s langen Telemetrie-Upload, währenddessen das Gerät nicht
  antwortet, und rät zu mehr als 8 s Timeout. Sie beruht teils auf dekompiliertem Code und ist nicht
  von Marstek bestätigt. Der Adapter gab bisher nach 3 s auf.

Die Ursache der langen Ereignisse ist ungeklärt und liegt vermutlich im Gerät.

## Betrachtete Optionen

### Option A — Länger warten, im Aussetzer weniger senden, Sollwert danach erneuern (gewählt)

- Dafür: Kurze Aussetzer werden unsichtbar, der Rückfall des Geräts wird kürzer, und alle
  Sicherheitsregeln der Bridge gelten weiter. Keine Änderung an den Entitäten.
- Dagegen: Heilt die langen Ereignisse nicht. Schreibbefehle warten im Aussetzer bis zu 9 s.

### Option B — Letzte Messwerte bis zu 120 s weitergeben

- Dafür: Das HEMS bliebe auch bei langen Ereignissen ohne Standby.
- Dagegen: Das HEMS regelte mit veralteten Istwerten, während der Speicher real auf 0 W oder -150 W
  steht. Ändert die Ausfallsemantik des Vertrags.

### Option C — Modbus TCP

- Dagegen: Die Upload-Blockade ist laut der Analyse gerade auf Modbus gemessen. Vom User bewusst
  zurückgestellt.

### Option D — Letzten Sollwert im Adapter wiederholen

- Dagegen: Umginge Pause und Lebenszeichen und könnte einen veralteten Sollwert senden, wenn der
  letzte Schreibversuch gescheitert ist. Deshalb erneuert die Bridge über `_async_sync()`.

## Entscheidung

Option A:

- Marstek-Wartezeit 3 Versuche à 3 s statt à 1 s, eine normale Antwort kommt weiter sofort.
- Nach einem gescheiterten Aufruf bis zur nächsten Antwort nur noch ein Versuch je Aufruf. Sonst
  stauten sich wartende Aufrufe hinter dem Lock, und das Gerät bekäme weiter Paketserien.
- Poll-Takt im Aussetzer je Adapter (`failed_poll_interval`): Marstek 10 s statt 30 s, E3DC
  unverändert 30 s, weil er seinen Sollwert ohnehin alle 5 s bekommt.
- Nach einem gescheiterten Poll oder gemeldetem Aussetzer (`StorageState.communication_interrupted`)
  ruft der Coordinator `HemsBridge.async_resync()` auf. Das sendet die aktuelle Anforderung sofort
  statt erst beim nächsten Keep-Alive. Ohne Zero-Schritt, die Betriebsart ändert sich dadurch nicht.
- Info-Log für die Messung: langsame Antworten, Dauer eines Aussetzers, Antworten mit fremder `id`.
  Antworten mit fremder `id` werden weiter verworfen.

## Folgen

- **Positiv:** Kurze Aussetzer lösen weder `unavailable` noch HEMS-Standby aus. Die selbstständige
  Abgabe des Speichers nach einem Aussetzer sollte deutlich kürzer werden.
- **Negativ:** Ein echter Ausfall wird erst nach 9 s gemeldet. Das HEMS regelt in dieser Zeit mit dem
  letzten Messwert.
- **Aufwand:** Vertragstext in beiden Repos, kein HEMS-Code.

## Rücknahmebedingung

Messung über rund 24 h mit Info-Log gegen die Zahlen oben. Bleiben kurze Ausfälle in gleicher Zahl
bestehen, stimmt die Annahme zur Dauer der Aussetzer nicht. Führt das sofortige Senden zu mehr
langen Ereignissen, wird `async_resync()` zurückgenommen. Bestätigt die Messung abweichende `id`s als
Fehlerquelle, wird die `id`-Prüfung neu bewertet.
