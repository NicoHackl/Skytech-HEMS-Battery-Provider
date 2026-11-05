# D-022: Marstek zusätzlich über Modbus TCP anbinden

- **Datum:** 05.11.2026
- **Status:** Aktiv, an Hardware noch nicht abgenommen
- **Betrifft:** `adapters/marstek_modbus.py`, `__init__.py`, `config_flow.py`, `const.py`,
  `strings.json`, `translations/de.json`, HEMS-Vertrag (Freigaben, Keep-Alive, Unload)
- **Ergänzt:** D-006 (Hersteller × Protokoll), D-007 (Transport UDP), D-021

## Kontext

Die UDP-API der Venus E 3.0 setzt seit Firmware V150 aus, D-021 verkürzt die Folgen, verhindert die
Ereignisse aber nicht. Am 05.11.2026 lief dasselbe Gerät mit der
[Marstek Modbus Suite](https://github.com/sphings79/marstek-modbus-suite) und einem HA-Skript
(Firmware V150.116.115). Dabei zeigten sich drei Effekte:

| Effekt | Beobachtung | Einordnung |
|---|---|---|
| A | Timeout und Neuverbindung rund alle 35 min, Leistung rund 20 s auf 0 W | Passt zum in der Suite beschriebenen Netzwerkchip-Reset. `binary_sensor.acspeicher1_cloud_status` stand auf aus. Nicht von Marstek bestätigt. Vom Adapter nur abzufangen. |
| B | „Received unexpected response“ nur beim Schreiben von 42000, 42010, 42020, 42021, 57-mal seit 10:29 | Der Befehl kam an. Das Skript läuft mit `mode: restart` und bricht einen laufenden Schreibbefehl im HEMS-Takt ab. Vermutlich trifft das den rund 4 s langen Telemetrie-Upload. |
| C | 42000 fiel um 07:36 und 08:46 von selbst aus, jeweils nach A | Das Gerät bestätigt Befehle dann weiter, führt sie aber nicht aus. |

Die Rampen und die unangeforderte Abgabe aus D-021 traten unter Modbus nicht auf: im Standby blieben
die Stundenmaxima ab 11 Uhr bei höchstens 10 W.

**Sicherungstest (05.11.2026, 17:31–17:34:55):** Mit 100 W Entladen, Freigabe an und ohne
Schreibbefehl hielt der Shelly rund -102 W über mindestens 200 s, der Modus blieb auf Entladen. Nur
die Abfragen liefen weiter. Über Modbus gibt es also keine Sicherung wie `cd_time` über UDP. Ob reine
Abfragen eine solche Sicherung zurücksetzen, ist nicht getestet.

## Betrachtete Optionen

### Option A — Eigener kleiner Modbus-Client im Adapter (gewählt)

Keine neue Abhängigkeit, das Zeitverhalten der Suite ist übernommen, kein Abbruch laufender Befehle.
Nachteil: Der Rahmenaufbau wird selbst gepflegt, die Fehlerrahmen der Firmware selbst behandelt.

### Option B — `pymodbus`

Fertiger Client. Abgelehnt: Die Suite umgeht darin mehrere Eigenheiten der Firmware, und die
Abhängigkeit wäre schwerer als die benötigten Funktionen FC03 und FC06.

### Option C — Suite und HA-Skript behalten

Kein Code. Abgelehnt: Die Steuerung läge außerhalb des Providers, Effekt B bliebe, und das
`StorageAdapter`-Prinzip wäre durchbrochen.

## Entscheidung

Der neue `MarstekModbusAdapter` erfüllt dasselbe `StorageAdapter`-Protocol wie die anderen. Coordinator,
Plattformen, HEMS-Anbindung und Schnittstellen-Entität bleiben unverändert. Im ersten Config-Flow-Schritt
stehen „Marstek (UDP)“, „Marstek (Modbus)“ und „E3DC“. Bestehende Einträge laufen unverändert weiter.

- **Lesen:** 34002 (SoC), 30006 (AC-Leistung), 42000, 42010. Lesen schreibt nie.
- **Schreiben:** bei Bedarf 42000 an, dann Leistung 42020 oder 42021, dann Modus 42010. Nur Änderungen
  und nach 55 s erneut, damit der 60-s-Keep-Alive wirkt. 0 W heißt Standby.
- **Zeitverhalten wie die Suite:** ein Request zur Zeit, 80 ms Abstand, 6 s Timeout, zwei Versuche,
  0,3 s Wartezeit vor einer Neuverbindung, Backoff 1–30 s. Im Aussetzer ein Versuch je Register.
- **Effekt A:** Nach einer Neuverbindung meldet der Adapter `communication_interrupted`, die Bridge
  sendet den Sollwert sofort (D-021).
- **Effekt B:** Eine Operation läuft unter einer Sperre bis zum Ende und wird von neuen Sollwerten
  nicht abgebrochen. Verspätete Antworten werden per Transaktions-ID verworfen, die Fehlerrahmen der
  Firmware fest mit 9 Byte gelesen.
- **Effekt C:** Jeder Poll vergleicht 42000 und 42010 mit dem Erwarteten. Bei Abweichung kommt der
  Sollwert erneut. Verlorene Freigabe wird einmal als Warnung geloggt.
- **Beenden (Entscheidung des Users):** Beim Entladen des Eintrags und beim HA-Stopp setzt `close()`
  42010 auf Standby, 42000 bleibt an. Hat der Adapter nie gesteuert, schreibt er nichts. Dafür
  schließt der Provider den Adapter nun auch bei `EVENT_HOMEASSISTANT_STOP`.

## Konsequenzen

- Ein Verbindungstest im Config-Flow ändert nichts am Gerät. Der erste Sollwert nimmt es aus dem
  App-Modus.
- Fällt HA ohne geordnetes Beenden aus oder ist die Bridge pausiert, läuft ein Sollwert unbegrenzt
  weiter (siehe [bekannte-luecken.md](../bekannte-luecken.md) und HEMS-Vertrag).
- Temperatur, Nennkapazität und Lade-/Entladefreigabe des Geräts liest der Adapter nicht. Die Freigabe
  gilt als frei, Sperren kommen aus dem Soll/Ist-Vergleich (D-018).
- Nur ein Modbus-Client ist möglich. `marstek_modbus` und der Skriptaufruf müssen vor der Umstellung
  raus. Für gleiche Entitäts-IDs wird der alte UDP-Eintrag zuerst gelöscht.
- Effekt A bleibt: Rund 20 s Unterbrechung rund alle 35 min sind vom Adapter nicht zu verhindern,
  solange die Ursache im Gerät besteht.
- Ein Modbus-Aufruf gilt nach bis zu 12 s als gescheitert, im Aussetzer nach 6 s.
