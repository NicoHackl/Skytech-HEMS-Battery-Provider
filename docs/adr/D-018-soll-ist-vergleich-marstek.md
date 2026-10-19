# D-018 — Soll/Ist-Vergleich für den Marstek

**Datum:** 19.10.2026 · **Status:** Aktiv

## Kontext

D-017 liest die Lade- und Entladefreigabe des Marstek aus `Bat.GetStatus` (`charg_flag`,
`dischrg_flag`). Am 19.10.2026 hat der User das gezielt geprüft: Bei 12 % SoC senkte er das
HEMS-`soc_min` dreimal kurz auf 11 %. Das HEMS forderte Entladung an (06:40–06:50 bis 566 W,
07:37–07:38 bis 528 W, 07:49–07:50 bis 1228 W). Der Speicher bestätigte jeden Sollwert, entlud
aber nicht (Ist 0 W). `dischrg_flag` blieb dabei `true`. Das Gerät meldet seine Sperre also nicht.

## Entscheidung

- Der Marstek-Adapter vergleicht in jedem `read()` den zuletzt bestätigten Passive-Sollwert mit
  der Ist-Leistung derselben Richtung (`_ResponseCheck`). Das gilt für Laden und Entladen.
- Gezählt wird die Zeit, in der der Sollwert mindestens `response_check_min_request_w` beträgt
  und die Ist-Leistung unter `response_check_max_actual_w` bleibt. Die Zeit wird **über mehrere
  Anforderungen aufsummiert**, damit auch kurzes Pendeln (18.10.2026: 8–25 s je Anforderung)
  erkannt wird. Liefert das Gerät, fällt die Zeit der Richtung auf 0. Ein Zählschritt beträgt
  höchstens das doppelte Abfrageintervall.
- Ab `response_check_time_seconds` ist die Richtung gesperrt. Die Freigabe im
  Schnittstellen-Sensor wird `false`, der Sperrgrund ist `keine_reaktion_laden` bzw.
  `keine_reaktion_entladen`, und `sperre_bis_soc_prozent` zeigt die Freigabeschwelle.
- Freigabe: Entladen bei SoC ≥ Sperr-SoC + 1 %, Laden bei SoC ≤ Sperr-SoC − 1 %. Danach wird die
  nächste Anforderung neu geprüft; verweigert das Gerät erneut, sperrt es wieder mit neuem
  Bezugs-SoC.
- Parameter je Speicher im Options-Flow (wie das Abfrageintervall), nur beim Marstek.
  Defaults: 30 s, 100 W, 20 W; Erkennungszeit 0 schaltet den Vergleich ab.
- Die Sperre wird nicht gespeichert. Nach einem Neustart oder Neuladen kostet das höchstens einen
  Fehlversuch von Erkennungszeit-Länge.

Vom User so festgelegt: Der Vergleich gehört in den Provider, weil er nur liefert, ob der Speicher
lädt oder entlädt, und weil das je Speicher verschieden ermittelt wird. Vorerst gilt er nur für
den Marstek: Der E3DC-Weg (EMS-Statusbits) ist noch nicht negativ getestet.

## Verworfen

- **Vergleich im HEMS:** wäre geräteunabhängig, kennt aber die Eigenheiten des einzelnen
  Speichers nicht. Vom User verworfen.
- **Feste Werte im Code:** vom User verworfen, die Werte sind je Speicher einstellbar.

## Folgen

- Das HEMS braucht keine Änderung: Es wertet `entladen_freigegeben: false` schon aus (HEMS D-068),
  sobald `provider_entity` gesetzt ist, und gibt das Defizit an den nächsten Speicher.
- Je Fehlversuch fließt bis zur Erkennungszeit Leistung aus dem Netz.
- Liegt die tatsächliche Wiedereinschaltschwelle des Geräts höher als Sperr-SoC + 1 %
  (beobachtet: etwa 15–17 % bei einer Sperre ab 12 %), folgen mehrere kurze Fehlversuche, bis der
  Speicher wieder entlädt.
