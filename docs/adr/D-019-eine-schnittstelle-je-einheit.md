# D-019 — Eine Schnittstellen-Entität je Einheit

**Datum:** 20.10.2026 · **Status:** Aktiv · **Ersetzt teilweise:** D-017 (Sensor je Speicher),
D-018 (Ort des Soll/Ist-Vergleichs)

## Kontext

D-017 brachte einen Schnittstellen-Sensor **je Speicher** (`sensor.<prefix>_hems_schnittstelle`),
SkytechHEMS las ihn über das Feld `provider_entity` (HEMS D-068). Der User will das nicht so:
Jede Einheit (HEMS, jeder Provider) soll genau **eine** Entität `sensor.<einheit>_schnittstelle`
veröffentlichen, die alle Informationen für die anderen Teilnehmer enthält.

## Entscheidung (User, 20.10.2026)

- Diese Integration veröffentlicht `sensor.battery_provider_schnittstelle`:
  - State: `hems_entity_prefix` aller Einträge mit HEMS-Anbindung, durch Komma getrennt.
  - Je Speicher `<prefix>_ladefreigabe` und `<prefix>_entladefreigabe` (getrennt nach Richtung,
    damit eine Entladesperre das PV-Laden nicht mitsperrt und sich die Marstek-Sperre bei SoC +1 %
    lösen kann), `<prefix>_ladesperrgrund`, `<prefix>_entladesperrgrund` und bei einer
    Soll/Ist-Sperre `<prefix>_sperre_bis_soc_prozent`.
  - Ein nicht erreichbarer Speicher ist in beiden Richtungen gesperrt (`nicht_erreichbar`).
- SkytechHEMS veröffentlicht `sensor.hems_schnittstelle` mit Lebenszeichen und je Speicher den
  **Istwerten** aus seinen Sensoren. Lebenszeichen ist die Änderung von `zyklus_zaehler`;
  `sensor.skytech_hems_status` entfällt.
- Der Soll/Ist-Vergleich (D-018) rechnet mit diesen HEMS-Istwerten, weil die HEMS-Sensoren
  schneller sind als die Gerätewerte. Er gehört deshalb der HEMS-Anbindung (`response_check.py`),
  nicht mehr dem Adapter. Fehlen die Istwerte, pausiert er. Nur Adapter mit
  `response_check_supported` (Marstek) nutzen ihn.
- Sollwerte laufen weiter über die HEMS-Ausgabehelfer. Das HEMS liest SoC und Istleistung aus
  seinen eigenen konfigurierten Sensoren.
- Harter Umstieg, Vertrag HEMS ↔ Battery-Provider 2.0.

## Umsetzung

- `interface.py`: ein Objekt in `hass.data[DOMAIN]`; Einträge melden sich an und ab; jede
  Coordinator-Aktualisierung schreibt den Sensor neu (nur bei Änderung). Weil er über alle
  Config-Entries geht, ist er keine Registry-Entität.
- Der alte Sensor je Speicher wird beim Setup aus der Registry entfernt.

## Folgen

- Weniger Entitäten, eine feste Stelle für das HEMS; kein `provider_entity` mehr.
- HEMS und Provider müssen zusammen aktualisiert werden; sonst steht der Speicher auf 0 W.
- Der Sensor lässt sich in der Oberfläche nicht umbenennen.
