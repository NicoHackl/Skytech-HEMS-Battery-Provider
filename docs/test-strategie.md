# Teststrategie

## Befehle

```bash
uv sync             # zieht u. a. pytest-homeassistant-custom-component (den echten HA-Testkern)
pytest              # alle Tests
pytest <pfad>       # gezielt eine Datei
ruff check .              # Linting und Formatprüfung
```

`pytest` und `ruff check .` müssen vor jedem Commit fehlerfrei durchlaufen — siehe
[git-workflow.md](git-workflow.md). `uv sync` ist bei einer HA-Integration nicht optional leicht:
`custom_components/battery_bridge/__init__.py` importiert Home Assistant auf Modulebene wie jede
Integration — sobald ein Test auch nur ein Blatt unter `custom_components.battery_bridge.*`
importiert, zieht das den kompletten HA-Core mit. `pytest-homeassistant-custom-component` gehört
deshalb fest zu den Dev-Abhängigkeiten, keine optionale Gruppe.

## Testarten

| Art | Umfang | Ort |
|---|---|---|
| Adapter-Unit | Ein Adapter gegen einen gemockten Transport, keine echte Hardware/Netzwerk | `tests/adapters/` |
| Integration (HA-Kern) | Setup/Unload eines Entry, Coordinator, Config-Flow — gegen den echten `hass`-Testkern | `tests/test_*.py` |
| Regression | Ein konkret aufgetretener Bug, damit er nicht wiederkehrt | beim jeweiligen Modul |

Die Teststruktur spiegelt die Struktur des Quellcodes. Zu
`custom_components/battery_bridge/adapters/marstek_udp.py` gehört
`tests/adapters/test_marstek_udp.py`.

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

Zielwert: **80 %** (Annahme, kein Vorgabewert aus dem Plan — bei Bedarf mit dem User anpassen).
Coverage ist ein Warnsignal, kein Ziel an sich — 100 % Coverage ohne Zusicherungen im Test ist
wertlos. Ungetestet bleiben dürfen generierte Dateien und triviale Getter.

## Fixtures

Tests laufen ohne echten Socket — auch nicht auf `127.0.0.1`: `pytest-homeassistant-custom-
component` bringt `pytest-socket` mit und blockt jeden echten Socket standardmäßig, ein realer
UDP-Mock-Server wäre also ohnehin gegen die eigene Testinfrastruktur gelaufen. Stattdessen wird
`asyncio.get_running_loop().create_datagram_endpoint` selbst gemockt (siehe
`tests/adapters/test_marstek_udp.py::_connected_adapter`): ein `_FakeTransport` beantwortet jedes
`sendto()` synchron über eine Responder-Funktion, indem er die Antwort direkt in die
Protocol-Queue des Adapters legt — deterministisch, ohne Port-Bindung, ohne Race. Für
Coordinator- und Config-Flow-Tests wird stattdessen `MarstekUdpAdapter.connect()`/`read()` selbst
per `unittest.mock.AsyncMock` gepatcht, das Protokoll spielt dort keine Rolle mehr.

Die Antwort-Payloads in den Fixtures stammen aus der bestätigten Marstek-Protokoll-Doku (siehe
[bekannte-luecken.md](bekannte-luecken.md)), nicht frei erfunden — nur die Vorzeichenkonvention
von `bat_power` ist dort als unverifiziert markiert und in beide Richtungen getestet.
