# Bekannte Lücken und Stolpersteine

**Vor jeder Annahme lesen.** Diese Datei existiert, weil Doku und Code auseinanderlaufen. Steht
etwas in [architektur.md](architektur.md), heißt das nicht, dass es implementiert ist — hier steht,
wo nicht.

## Abweichungen Spec ↔ Code

| Thema | Doku sagt | Code macht | Folge für die Arbeit |
|---|---|---|---|
| Python-Version | `plan.md` Abschnitt 2 nannte Python 3.11 | `pyproject.toml` verlangt `>=3.13` | Aktuelles HA-Core und `pytest-homeassistant-custom-component` (Stand 09/2026) setzen Python ≥3.13 voraus — bei `uv sync` löste die Auflösung mit `<3.14` sonst nicht auf. Reine Umsetzungsanpassung an die Laufzeit, keine bewusste Design-Entscheidung, siehe [architektur.md](architektur.md). |

## Vor dem produktiven Schreibzugriff (M2) zu bestätigen

Die Mechanismus-Frage ist geklärt (siehe „Marstek-Protokoll — Quellenlage" unten): Passive-Mode
ist implementiert. Offen bleibt nur noch die Praxisprobe an echter Hardware — **kein Sollwert
wird ungeprüft an eine echte Anlage gesendet**, bevor das hier abgehakt ist:

| Frage | Betrifft | Blockiert |
|---|---|---|
| Sendet `write_charge_power`/`write_discharge_power` das richtige Vorzeichen? (`power` negativ = laden, positiv = entladen, aus zwei Quellen übereinstimmend übernommen — siehe unten) | `adapters/marstek_udp.py: _set_passive_power()` | Produktiver Einsatz von M2 |
| Tatsächliche Reaktionszeit auf eine geschriebene Leistungsvorgabe (bekannt ist nur „~3 s" für Selbstverbrauchsmodus mit CT002, nicht für eine direkte Vorgabe) | Poll-Intervall in `coordinator.py` | M2, Feintuning |

**Geklärt (04.09.2026):** Fällt das Gerät nach `cd_time` (300 s) tatsächlich in den vorherigen
Modus zurück, wenn kein neuer Sollwert kommt? **Ja** — per HA-Verlauf live bestätigt, siehe
„HEMS-Anforderung ‚hängt' nach 5 Minuten" weiter unten und [ADR D-012](adr/D-012-hems-keepalive.md).

## Marstek-Protokoll — Quellenlage

Marstek veröffentlicht die Local API nicht offiziell. Verwendet werden `Bat.GetStatus` (Feld
`soc`), `ES.GetStatus` (Felder `bat_soc`, `bat_power`) und `ES.SetMode` (Passive-Mode,
`passive_cfg: {power, cd_time}`) — zusammengetragen aus vier unabhängigen Community-Quellen:
[Randyocean/Marstek](https://github.com/Randyocean/Marstek/blob/main/docs/marstek_device_openapi.MD)
(Protokoll-Dump), [taurgis/has-marstek-local-api](https://github.com/taurgis/has-marstek-local-api),
[jaapp/ha-marstek-local-api](https://github.com/jaapp/ha-marstek-local-api) und
[leonscheltema/ha-marstek](https://github.com/leonscheltema/ha-marstek) — alle vier aktiv
gepflegt, Venus E 3.0 wird von mindestens taurgis ausdrücklich als unterstützt genannt
(Venus E2.0 ausdrücklich **nicht**).

**Lesepfad (`bat_power`) — Vorzeichenkonvention unverifiziert:** Randyocean dokumentiert
„positiv = entladen", der tatsächliche Code von taurgis liest das Gegenteil („positiv = laden")
und negiert es für die eigene Konvention. `adapters/marstek_udp.py` übernimmt die
taurgis-Lesart (aktiver, gepflegter Code wiegt schwerer als eine Doku-Kopie) — **vor dem
produktiven Einsatz an echter Hardware bestätigen** (Plan Abschnitt 5, Plan-Schritt 4): Speicher
laden lassen, prüfen, dass `sensor.<prefix>_ist_ladeleistung` und nicht
`..._ist_entladeleistung` den Wert zeigt.

**Schreibpfad (`ES.SetMode` Passive) — Mechanismus geklärt, Vorzeichen mit mittlerer
Zuversicht:** Alle vier Quellen setzen für einen direkten Leistungs-Sollwert übereinstimmend auf
Passive-Mode statt Manual-Mode (Manual ist für feste Tageszeitpläne). Für die Vorzeichenkonvention
des `power`-Felds stimmen jaapp und leonscheltema unabhängig überein: positiv = entladen, negativ
= laden — das deckt sich mit der (bereits negierten) HA-Anzeigekonvention aus dem Lesepfad, ist
aber nicht dieselbe Quelle wie der rohe `bat_power`-Wert und **ebenfalls nicht an echter Hardware
verifiziert**. Ein falsches Vorzeichen hier ist folgenreicher als beim Lesepfad — ein Sollwert
steuert echte Leistung, ein Lesewert nur eine Anzeige. Deshalb: erster produktiver Testlauf mit
kleinem Sollwert (z. B. 100 W) und Blick auf die tatsächliche Reaktion des Speichers, nicht
direkt mit einem Sollwert, der etwas kaputt machen kann.

## An echter Venus E 3.0 beobachtet (03.09.2026)

Erster Praxiskontakt der Integration mit einer echten Anlage. SoC-Anzeige und ein erstes manuelles
Setzen der Soll-Lade-/Entladeleistung funktionierten; danach zwei Auffälligkeiten:

- **`ES.SetMode`-Aufrufe der HEMS-Anbindung timeoueten fast durchgehend, `ES.GetStatus`
  (Coordinator-Poll) nur gelegentlich.** Ursache gefunden und behoben: `MarstekUdpAdapter`
  teilte eine einzige Antwort-Queue zwischen allen `_call()`-Aufrufen, ohne sie zu
  serialisieren — der Coordinator-Poll (fester 5-s-Takt) und die HEMS-Anbindung (eigener Task,
  ausgelöst bei jeder Änderung der HEMS-Anforderungshelfer, damit im Sekundentakt) liefen auf
  demselben Adapter parallel. Traf die Antwort auf Anfrage A ein, während eine andere Anfrage B
  gerade in ihrer eigenen Warteschleife auf die Queue wartete, konnte B sie zuerst aus der Queue
  holen, an der ID als fremd erkennen und per `continue` verwerfen (nicht zurücklegen) — A bekam
  seine eigene, korrekte Antwort nie zugestellt und timeoutete, obwohl das Gerät geantwortet
  hatte. Da die HEMS-Anbindung viel häufiger sendet als der Poll, traf es `ES.SetMode` fast
  immer. Fix: `asyncio.Lock` in `adapters/marstek_udp.py`, serialisiert jetzt jeden
  Request-Antwort-Zyklus vollständig — Test `test_gleichzeitige_aufrufe_teilen_sich_nicht_die_antwort`.
  **Live bestätigt** (03.09.2026, nach Update + Neustart): Coordinator-Polls laufen seither
  durchgehend mit `success: True`, die HEMS-Anbindung hat direkt nach dem Neustart erfolgreich
  auf `number.<prefix>_soll_ladeleistung`/`_soll_entladeleistung` geschrieben (auf `0.0`, ohne
  Fehler im Log) — vorher timeoutete genau dieser Aufruf praktisch immer.
- **Bestätigt per Debug-Log, Ersatzwert seit 03.09.2026 im Einsatz:** `sensor.<prefix>_ist_ladeleistung`/
  `_ist_entladeleistung` zeigten dauerhaft `unknown`. Rohantwort von `ES.GetStatus` auf der
  echten Anlage (03.09.2026, mehrere Polls hintereinander, alle `success: True`):
  ```json
  {"id": 0, "bat_soc": 85, "bat_cap": 5120, "pv_power": 0, "ongrid_power": 0,
   "offgrid_power": 0, "total_pv_energy": 0, "total_grid_output_energy": 26340,
   "total_grid_input_energy": 34452, "total_load_energy": 0}
  ```
  Das Feld `bat_power` fehlt **komplett** — kein Parsing-Fehler, das Gerät liefert es schlicht
  nicht mit. `Bat.GetStatus` (separat geprüft) hat laut Protokoll-Dump ohnehin kein
  Leistungsfeld (nur SoC, Lade-/Entladeflags, Temperatur, Kapazität). `EM.GetStatus` liefert nur
  CT-/Netzmessung (`a_power`/`b_power`/`c_power`/`total_power`), keine Batterieleistung. Damit
  ist `ES.GetStatus.bat_power` laut verfügbarer Doku der einzige Weg zur Ist-Leistung — und genau
  der fehlt hier.

  **Auffällig, nur Hypothese, nicht verifiziert:** `bat_cap: 5120` ist exakt das Doppelte der in
  den Referenz-Beispielen dokumentierten Standard-Venus-E-Kapazität (~2560). Passt zu einem
  Zwei-Batterie-Stack — möglich, dass `id: 0` in `ES.GetStatus`/`ES.SetMode` nur einen
  Aggregatwert ohne `bat_power` liefert, während einzelne Packs (`id: 1`/`id: 2`?) es hätten.
  Keine der vier Community-Quellen dokumentiert Mehrfach-Pack-Verhalten für `ES.GetStatus`, das
  ist reine Beobachtung aus einer Zahl, keine bestätigte Ursache. Für eine Code-Änderung dazu
  (z. B. andere `id`-Werte testen) weiterhin bei Marstek/den Community-Projekten nachfragen statt
  ungeprüft umzusetzen.

  **Ersatzwert eingebaut:** Der User hat händisch `ES.GetMode` abgefragt (siehe
  `terminal_ausschnitt.txt`) — auch dort fehlt `bat_power`, aber `ongrid_power`/`offgrid_power`
  sind vorhanden, genau wie in `ES.GetStatus`. Hypothese des Users, hier übernommen: `ongrid_power`
  ist an dieser Anlage (kein PV-Eingang direkt am Speicher, `pv_power` durchgängig 0) die
  tatsächliche Wirkleistung des Geräts auf der Netzseite — für ein reines AC-Batteriegerät ohne
  eigenen PV-Eingang praktisch identisch mit der Batterieleistung. Vorzeichen umgekehrt zu
  `bat_power`: positiv = Einspeisung (entladen), negativ = Bezug (laden). `read()` in
  `adapters/marstek_udp.py` nutzt das jetzt als Fallback, wenn `bat_power` fehlt (negiert, bevor
  es in dieselbe Aufteilung wie `bat_power` geht) — Tests:
  `test_read_nutzt_ongrid_power_wenn_bat_power_fehlt`,
  `test_read_ongrid_power_positiv_ergibt_entladeleistung`,
  `test_read_ignoriert_ongrid_power_wenn_bat_power_vorhanden`. **Weiterhin nicht offiziell
  bestätigt** — deckt nur den Netz-Anteil ab, ein aktiver Offgrid-/Backup-Kreis (`offgrid_power`)
  ginge in dieser Leistung unter; vor produktivem Vertrauen in den Wert an echter Hardware über
  eine volle Lade-/Entladephase mit der Marstek-App gegenprüfen.

  **Erster Cross-Check nach Deploy (03.09.2026, 21:58):** `sensor.ac_speicher_1_ist_entladeleistung`
  zeigte 404 W, das unabhängig vom Shelly-Stromzähler gemessene `sensor.ac_speicher_1_leistung`
  im selben Moment −408,6 W — Größenordnung und Richtung passen zusammen. Kein Beweis über eine
  volle Phase, aber ein starkes erstes Indiz, dass die Vorzeichenannahme stimmt.

## Speicher springt unter HEMS-Steuerung (gemeldet 03.09.2026)

User-Beobachtung: Unter der HEMS-Anbindung dieser Integration „springt" der Speicher ständig —
über die alte Modbus-Automation (`script.venus_e_1_steuerung`, `mode: queued`, direkt auf zwei
unabhängige Ladeleistung-/Entladeleistung-Modbus-Register geschrieben) lief dieselbe, von HEMS
berechnete Anforderung „relativ gut". Ursache liegt nicht an HEMS' Anforderungswert selbst — der
ist nachweislich unruhig (Logbuch zeigt `input_select.ems_<prefix>_anforderung_betriebsart` über
Minuten hinweg im 3–30-Sekunden-Takt zwischen `entladen`/`standby` wechselnd, `input_number...
_anforderung_leistung_w` ähnlich volatil) — Ursache ist, wie `hems_bridge.py` bislang darauf
reagierte, kombiniert mit einer Eigenheit des Marstek-Schreibpfads:

`write_charge_power()`/`write_discharge_power()` sind bei Passive-Mode **kein** additives
Zwei-Kanal-Signal wie die zwei separaten Modbus-Register der alten Automation, sondern derselbe
einzige `passive_cfg.power`-Sollwert (siehe `adapters/marstek_udp.py`) — der zuletzt gesendete
Aufruf gewinnt vollständig. `hems_bridge._async_sync()` hat bisher bei **jedem** Sync zuerst die
inaktive Richtung auf 0 gesetzt, bevor die aktive Richtung geschrieben wurde — auch dann, wenn
sich nur der Betrag der ohnehin aktiven Richtung änderte und die Betriebsart gar nicht wechselte.
Bei einer nur alle paar Sekunden neu berechneten Anforderung heißt das: zwei Befehle
hintereinander auf **dasselbe** Gerätefeld — erst 0, dann der neue Zielwert — bei jeder einzelnen
Anpassung. Am Speicher kam das als kurzer, wiederholter Sprung auf 0 W an, nicht als sanfte
Anpassung.

**Fix:** `hems_bridge.py` merkt sich jetzt die zuletzt erfolgreich angewendete Betriebsart und
setzt die inaktive Richtung nur noch bei einem tatsächlichen Wechsel auf 0 — bleibt die
Betriebsart gleich, geht nur noch die aktive Richtung mit dem neuen Wert raus, ohne
Zero-Zwischenschritt. Tests:
`test_gleichbleibende_betriebsart_setzt_inaktive_richtung_nicht_erneut_auf_null`,
`test_wechsel_der_betriebsart_setzt_inaktive_richtung_erneut_auf_null`,
`test_nach_fehlgeschlagenem_wechsel_wird_beim_naechsten_sync_erneut_genullt`.

**Nicht behoben, separate Beobachtung:** Dass die HEMS-Anforderung selbst (Betriebsart **und**
Leistung) so häufig kippt, ist unabhängig von dieser Integration — das ist der rohe Wert, den
auch die alte Modbus-Automation empfangen hat. Ob das am Regelverhalten des SkytechHEMS-Add-ons
für die Geräteklasse `battery` liegt (kein sichtbares HA-`script`/`automation` dafür gefunden —
`script.ems_regler_berechnen` behandelt nur Heizstab/Wallbox/Heizlüfter, nicht den Speicher; die
Berechnung für `battery` läuft demnach im Python-Add-on selbst) oder eine andere Ursache hat, ist
außerhalb dieses Repos zu klären.

## HEMS-Anforderung „hängt" nach 5 Minuten (gemeldet 04.09.2026, behoben)

User-Beobachtung: Speicher lädt manchmal nicht, obwohl `sensor.<prefix>_hems_soll_ladeleistung`
weiterhin z. B. 2500 W zeigt — Aus-/Einschalten von `switch.<prefix>_hems_steuerung_aktiv` bringt
die Anbindung jedes Mal wieder zum Laufen, bis zum nächsten Mal. War schon mehrfach aufgetreten.

Per `ha_get_history` (HA-Verlauf) rekonstruiert, zwei Vorfälle am 04.09.2026:

| Letzter tatsächlich gesendeter Sollwert | Ladung stoppt (`sensor.<prefix>_ist_ladeleistung` → 0) | Abstand |
|---|---|---|
| 13:37:08 | 13:42:12 | 304 s |
| 13:44:02 | 13:49:02 | 300 s |

Beide Abstände treffen exakt `cd_time` (`_PASSIVE_MODE_DURATION_S` = 300 s,
`adapters/marstek_udp.py`) — den Sicherheits-Watchdog des Marstek-Passive-Mode: läuft er ab, ohne
dass ein neuer Sollwert kommt, fällt das Gerät aus dem Passive-Mode zurück. Beantwortet damit die
bis dahin offene Frage weiter oben in dieser Datei — ja, das Gerät fällt tatsächlich zurück.

**Ursache:** `hems_bridge.py` synchronisierte bislang rein ereignisgetrieben
(`async_track_state_change_event` auf die beiden HEMS-Anforderungshelfer). Blieb die HEMS-
Anforderung mehrere Minuten exakt unverändert, feuerte kein Helferevent mehr, also lief
`_async_sync()` nicht erneut — obwohl der zuletzt gesendete Sollwert weiterhin gilt. Der Watchdog
kennt diesen Unterschied nicht: er verlangt einen neuen Aufruf, unabhängig davon, ob sich der Wert
geändert hat. `sensor.<prefix>_hems_soll_ladeleistung` zeigte in dieser Zeit weiterhin den zuletzt
erfolgreich gesendeten (jetzt veralteten) Wert — sieht aus wie „Anforderung da, Speicher ignoriert
sie", ist tatsächlich „Anforderung ist zu alt, Gerät hat sie selbst verworfen". Kein Fehler im
Log, weil kein Schreibvorgang fehlschlägt — es wird schlicht keiner mehr versucht. Widerlegt
außerdem eine bisherige Design-Annahme (D-008): SkytechHEMS sendet **nicht** von sich aus erneut,
solange sich der Anforderungswert nicht ändert.

**Fix:** `hems_bridge.py` sendet den aktuellen Sollwert jetzt zusätzlich alle 60 s erneut
(`HEMS_KEEPALIVE_INTERVAL`, `const.py`, `async_track_time_interval`) — deutlich unter den 300 s
von `cd_time`, unabhängig davon, ob sich die HEMS-Anforderung seitdem geändert hat. Kein
Zero-Zwischenschritt bei unveränderter Betriebsart (bestehende `mode_changed`-Logik, siehe
„Speicher springt" oben, gilt unverändert für Keep-Alive-Ticks). Tests:
`test_keepalive_sendet_unveraenderten_sollwert_erneut`,
`test_keepalive_sendet_nichts_waehrend_pause`,
`test_unload_entfernt_auch_den_keepalive_listener`. Ausführlich:
[ADR D-012](adr/D-012-hems-keepalive.md).

## Verbindung reißt ab, nur Neuladen half (gemeldet 10.09.2026, behoben)

User-Beobachtung: Über mehrere Stunden/Tage standen sämtliche Entities des Speichers auf „nicht
verfügbar", die HEMS-Anbindung setzte keinen Sollwert mehr. Nach einem Neuladen der Integration
lief wieder alles.

Per HA-Verlauf (`sensor.<prefix>_ladezustand`, `switch.<prefix>_hems_steuerung`) und Systemlog
rekonstruiert — vier Ausfälle:

| Beginn | Ende | Dauer | Ausgang |
|---|---|---|---|
| 09.09.2026 03:54:46 | 03:56:31 | 105 s | selbst erholt |
| 09.09.2026 11:11:06 | 11:22:45 | 11,6 min | selbst erholt |
| 10.09.2026 03:21:52 | 03:21:55 | 3 s | selbst erholt |
| 10.09.2026 04:09:31 | 05:45:43 | 96 min | erst durch Neuladen |

Im gesamten Zeitraum 114 Meldungen im 60-s-Takt des Keep-Alive:
`Marstek <host>:30000 antwortet nach 3 Versuchen nicht auf ES.SetMode.`

**Beweis, dass nicht das Gerät weg war:** `sensor.<prefix>_hems_soll_entladeleistung` ging um
05:45:43.358 auf `unavailable` (Entry wird entladen) und um 05:45:43.703 zurück auf `0.0` (Entry
wieder eingerichtet). Dieser Sensor zeigt nur dann einen Wert, wenn die HEMS-Anbindung mindestens
einmal erfolgreich geschrieben hat — der erste Schreibvorgang auf dem frisch erzeugten Socket kam
also binnen 345 ms durch. Der Speicher war die ganze Zeit erreichbar, tot war der UDP-Socket.
Als Nebenursache ausgeschlossen: die parallel installierte Modbus-Integration für dasselbe Gerät
ist in HA deaktiviert und nicht geladen, es gab also keinen zweiten Client.

**Ursache:** `adapters/marstek_udp.py` erzeugte seinen Transport genau einmal. Home Assistant ruft
`connect()` nur aus `coordinator._async_setup()` auf, und das läuft ausschließlich beim ersten
Refresh eines Entry. Stirbt der Socket danach, ist jedes weitere `sendto()` ein stiller No-Op —
keine Exception, kein Logeintrag; aus Adaptersicht sieht das aus wie ein Gerät, das nicht mehr
antwortet. `_MarstekUdpProtocol` implementierte kein `connection_lost()`, und `_call()` prüfte nur
auf `self._transport is None`, was ausschließlich beim Entladen des Entry eintritt. Es gab keinen
Weg zurück außer Neuladen.

**Fix (D-013):** Der Adapter prüft vor jedem Aufruf selbst, ob der Transport noch lebt
(`connection_lost()`, `is_closing()`), und verwirft ihn zusätzlich nach
`_RECONNECT_AFTER_FAILED_CALLS` (2) erfolglosen Aufrufen hintereinander — der nächste Aufruf
erzeugt dann einen frischen Socket mit neuem Quellport, also genau das, was vorher nur ein
manuelles Neuladen bewirkt hat. Die Antwort-Queue wird vor jedem Aufruf geleert, damit eine
verspätete Antwort eines abgelaufenen Requests nicht im nächsten Aufruf landet. Während eines
Ausfalls streckt der Coordinator seinen Takt auf `FAILED_UPDATE_INTERVAL` (30 s), statt weiter im
Normaltakt mit je drei Versuchen zu senden. Tests:
`test_geschlossener_transport_wird_vor_dem_naechsten_aufruf_neu_aufgebaut`,
`test_connection_lost_erzwingt_den_neuaufbau`,
`test_reconnect_erst_nach_mehreren_erfolglosen_aufrufen`,
`test_erfolgreicher_aufruf_setzt_den_fehlerzaehler_zurueck`,
`test_alte_antwort_gilt_nicht_als_antwort_auf_den_naechsten_request`,
`test_poll_intervall_wird_bei_fehler_gestreckt_und_bei_erfolg_zurueckgesetzt`. Ausführlich:
[ADR D-013](adr/D-013-udp-reconnect.md).

**Zeitliche Korrelation, mittlerweile behoben (D-014):** Am 08.09.2026 um 09:22 wurde das
Poll-Intervall von 5 s auf 1 s gesenkt (Commit `2e79878`, über `origin/main` `8062b7f`
ausgeliefert — genau der Stand, der zum Zeitpunkt der Ausfälle lief). Der erste Ausfall trat am
Folgetag auf, davor gab es keinen. Ein Poll je Sekunde ist für den Netzwerkteil des Marstek viel:
ein erfolgloser Poll blockiert bereits drei Sekunden (drei Versuche à 1 s), und derselbe
`_call_lock` trägt zusätzlich die Schreibvorgänge der HEMS-Anbindung. Bewiesen ist der
Zusammenhang nicht, plausibel schon. Das Intervall ist seit D-014 kein globaler Fixwert mehr,
sondern pro Gerät über Config-/Options-Flow konfigurierbar (`CONF_UPDATE_INTERVAL`, 1–60 s,
Default 5 s) — der Reconnect oben bleibt die Absicherung darunter, unabhängig vom gewählten Takt.
Der User hat daneben eine eigene, nicht Teil dieser Integration seiende Alternativlösung für eine
schnelle Leistungsabfrage. **Treten weiterhin Ausfälle auf, ist ein zu niedrig gewähltes
Poll-Intervall der erste Kandidat**, bevor an anderer Stelle gesucht wird.

**Zweiter Teil des Fixes — der Ausfall war unsichtbar:** `sensor.<prefix>_hems_soll_entladeleistung`
zeigte die vollen 96 Minuten unverändert `0.0`, weil die beiden HEMS-Soll-Sensoren nur am zuletzt
*erfolgreichen* Schreibvorgang hängen. `hems_bridge.py` führt jetzt `write_ok`: solange der letzte
Schreibversuch gescheitert ist, sind beide Sensoren „nicht verfügbar", statt einen Wert zu zeigen,
den niemand bestätigt hat. Gemeldet wird außerdem nur noch der Beginn einer Ausfallphase als
Fehler und ihr Ende als Warnung — vorher stand dieselbe Zeile 114-mal im Log. Tests:
`test_wiederholter_schreibfehler_wird_nur_einmal_als_fehler_geloggt`,
`test_erfolgreicher_sync_nach_fehler_meldet_wieder_ok`,
`test_hems_sensoren_sind_bei_schreibfehler_nicht_verfuegbar`.

## Stolpersteine

Dinge, die schon einmal Zeit gekostet haben:

- **`StorageAdapterError`-Meldungen sind für das Log geschrieben, nicht für den Nutzer.** Sie
  enthalten bewusst Host, Port, JSON-RPC-Methodennamen und rohe Antwort-Dicts (siehe
  `adapters/marstek_udp.py`) — wertvoll beim Debuggen, aber ein Verstoß gegen Regel 12, sobald sie
  unverändert in eine `HomeAssistantError` wandern. Genau das ist `number.py` passiert (siehe
  CHANGELOG.md). Ein künftiger zweiter Adapter (D-006) muss dasselbe Muster einhalten: technisch
  loggen, dann eine eigene Nutzermeldung bauen — nie `str(exc)` direkt an eine HA-Exception geben.
- **`number.<prefix>_soll_ladeleistung`/`_soll_entladeleistung` zeigen nicht, was die
  HEMS-Anbindung gerade wirklich sendet.** `hems_bridge.py` schreibt direkt auf den Adapter
  (`adapter.write_charge_power()`/`write_discharge_power()`), nie über die Number-Entity selbst
  (`async_set_native_value()`) — deshalb bleibt `_attr_native_value` der Entity unverändert bei
  ihrem Startwert `0.0` bzw. beim letzten manuell über die Entity gesetzten Wert, während der
  Speicher tatsächlich einen ganz anderen, von HEMS vorgegebenen Sollwert bekommt (beobachtet
  03.09.2026: Entity zeigte `0.0`, während die Anlage mit −417 W entlud). Kein Bug im Sinne von
  falschem Verhalten — Adapter-Aufruf und Entity-Anzeige sind schlicht zwei getrennte Pfade —
  aber irreführend für jeden, der aus der Entity-Anzeige den aktuellen Sollwert abliest, solange
  eine HEMS-Anbindung aktiv ist. Seit D-013 gilt zusätzlich: erreichen die Sollwerte das Gerät
  nicht mehr, verschwinden die HEMS-Soll-Sensoren, statt einen unbestätigten Stand
  weiterzuzeigen — `number.<prefix>_soll_*` bleibt davon unberührt und zeigt weiterhin nur, was
  zuletzt von Hand über die Entity gesetzt wurde. **Verhalten von `number.py` bleibt unverändert** (Absicht: die
  Number-Entities sind für manuelles Bedienen da, nicht als Anzeige der HEMS-Anbindung) — seit
  0.3.0 gibt es aber einen korrekten Ablesepunkt daneben:
  `sensor.<prefix>_hems_soll_ladeleistung`/`_hems_soll_entladeleistung` zeigen genau den Wert,
  den `hems_bridge.py` zuletzt erfolgreich an den Adapter gesendet hat (`HemsBridge.last_command`,
  siehe `docs/datenmodell.md`) — nur vorhanden, wenn für den Speicher ein HEMS-Präfix eingerichtet
  ist. Siehe CHANGELOG.md `[0.3.0]`.

## Offene Bugs

Noch keine.

## Vor dem produktiven Einsatz der HEMS-Anbindung (`hems_bridge.py`) zu bestätigen

Dieselbe Vorsicht wie bei M2 (siehe oben) — die Übersetzungslogik selbst ist getestet, aber die
Schreibaufrufe, die sie auslöst, laufen über denselben unverifizierten Marstek-Schreibpfad:

| Frage | Betrifft | Blockiert |
|---|---|---|
| Löst ein Wechsel von `laden`/`entladen`/`standby` am Gerät tatsächlich die erwartete Richtung aus, in der von `hems_bridge.py` gewählten Reihenfolge (inaktiv zuerst auf 0)? | `hems_bridge.py: _async_sync()` | Aktivierung der HEMS-Anbindung an echter Hardware |
| Solange die HEMS-Anbindung für einen Entry aktiv ist, überschreibt sie laufend die eigenen `number.*_soll_*`-Entities — manuelles Bedienen dieser Entities in diesem Zustand wird vom nächsten HEMS-Zyklus (Sekundentakt) sofort wieder verworfen. **Seit 0.4.0 gezielt vermeidbar:** `switch.<prefix>_hems_steuerung_aktiv` (D-011) ausschalten, bevor `number.*_soll_*` manuell bedient wird — steht nach dem nächsten Neustart wieder auf EIN. | `number.py` vs. `hems_bridge.py` | Kein Bug, aber überraschend, wenn nicht dokumentiert |

## Bewusst nicht umgesetzt

| Thema | Warum nicht | Verweis |
|---|---|---|
| Weitere Hersteller/Protokolle (Modbus TCP, HTTP/REST, MQTT) | Kein aktueller Bedarf, Marstek UDP deckt den Start | D-006, [roadmap.md](roadmap.md) |

---

Wird ein Punkt behoben, wird er hier **gelöscht** und im [CHANGELOG.md](../CHANGELOG.md) vermerkt.
Eine Liste voller erledigter Einträge liest niemand mehr.
