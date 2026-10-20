# Projektübergreifende Verträge

Die Verträge folgen der gemeinsamen Struktur der Skytech-Projekte:

```text
contract/
├── README.md
└── contract_<projektpaar>/
    ├── <vertragsdatei>.md
    └── <zugehoerige-plaene>.md  # falls vorhanden
```

Jedes Projektpaar besitzt einen eigenen Ordner. Der gemeinsame Vertrag liegt unter
demselben relativen Pfad und wortgleich in beiden beteiligten Repositories. Änderungen
an der Schnittstelle werden im selben Arbeitspaket in beiden Kopien nachgezogen.

Der Status im Vertrag unterscheidet implementierten Austausch, bekannte Grenzen
und Entwürfe. Ein Plan oder eine Dokumentationsänderung allein implementiert keine
Schnittstelle. Lokale Dokumentation verlinkt den Vertrag, statt eine abweichende
Beschreibung der gemeinsamen Felder zu führen.

## Grundsatz: eine Schnittstellen-Entität je Einheit

Seit 20.10.2026 (Entscheidung des Users) veröffentlicht jede Einheit — SkytechHEMS, jeder
Provider — genau **eine** Entität `sensor.<einheit>_schnittstelle`, die alle Informationen für
alle anderen Teilnehmer enthält (Werte als Attribute, je Gerät mit dessen Präfix vorne).
Umgesetzt: `sensor.hems_schnittstelle` (Lebenszeichen, Istwerte der Speicher) und
`sensor.battery_provider_schnittstelle` (Freigaben der Speicher). Sollwerte laufen weiter über die
`input_*`-Ausgabehelfer. Offen: die Paare HEMS ↔ Energy-Pilot, HEMS ↔ Powerflow-Card und
HEMS ↔ Data-Insight folgen in eigenen Arbeitspaketen.

| Gegenstelle | Vertrag | Stand / Hinweise |
|---|---|---|
| HEMS | [contract_hems_battery_provider.md](contract_hems_battery_provider/contract_hems_battery_provider.md) | Aktueller Austausch einschließlich dokumentierter Betriebsgrenzen; Version 2.0: je Einheit eine Schnittstellen-Entität (`sensor.hems_schnittstelle`, `sensor.battery_provider_schnittstelle`); Marstek-Freigaben per Soll/Ist-Vergleich mit HEMS-Istwerten; E3DC-Statusbits noch nicht negativ getestet. |
