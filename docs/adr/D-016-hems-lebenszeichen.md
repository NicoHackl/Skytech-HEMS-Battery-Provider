# D-016 — HEMS-Lebenszeichen

**Datum:** 07.10.2026 · **Status:** Aktiv

## Kontext

Der Keep-Alive (D-012) sendet den aktuellen HEMS-Helferwert regelmäßig erneut. Steht SkytechHEMS
still, während Home Assistant weiterläuft, hielt er damit einen alten Lade- oder Entladesollwert
unbegrenzt aktiv. Am Alter der Helfer ist ein Ausfall nicht erkennbar: das HEMS schreibt
unveränderte Werte bewusst nicht neu.

## Entscheidung

- SkytechHEMS veröffentlicht je Zyklus `sensor.skytech_hems_status` (HEMS D-062). Vertrag:
  `contract/contract_hems_battery_provider/contract_hems_battery_provider.md`.
- `heartbeat.py` bewertet die Frische mit der eigenen monotonen Uhr anhand der Änderung des
  Zählers; Frist `hems_timeout_factor` × `zyklus_intervall_s` (Options-Flow, Default 3), sonst 90 s.
- Der beim Start vorgefundene Wert ist nur Ausgangslage. Bis zur ersten danach gesehenen Änderung
  steht der Speicher auf 0 W — ein alter positiver Sollwert löst nach einem Neustart nichts aus.
- Nicht frisch: beide Richtungen 0 W, auch im Keep-Alive-Takt (E3DC übernähme sonst nach 10 s
  selbst). Eine eigene Prüfung alle 5 s sorgt dafür, dass der Stopp nicht erst mit dem nächsten
  Marstek-Keep-Alive (60 s) kommt.
- Pausiert (D-011) wird das Lebenszeichen nicht ausgewertet; auch die HEMS-Notabschaltung
  übersteuert die Pause nicht — so entschieden.

## Folgen

- Ohne laufendes HEMS-Add-on bleibt ein Speicher mit HEMS-Präfix dauerhaft auf 0 W. Wer ihn ohne
  HEMS betreiben will, pausiert die Anbindung oder entfernt das Präfix.
- Die HEMS-Soll-Sensoren zeigen im Stoppzustand 0, weil genau das gesendet wurde.
