# D-017 — Gerätestatus und Schnittstellen-Sensor zum HEMS

**Datum:** 18.10.2026 · **Status:** Aktiv

## Kontext

Am 18.10.2026 forderte SkytechHEMS von 09:01 bis 09:16 beim Marstek `acspeicher1` eine Entladung
an. Die Integration sendete sie, das Gerät bestätigte den Passive-Mode-Sollwert, entlud aber nicht
(Shelly: rund 8 W Leerlauf). Das trat in den drei Tagen davor nur bei 12–15 % SoC nach einem
Wiederaufladen vom Boden auf. Das HEMS kennt eine solche Gerätesperre nicht: es teilte das ganze
Hausdefizit dem Marstek zu, der E3DC bekam nichts, das Netz deckte den Bedarf.

Die Marstek Local API meldet in `Bat.GetStatus` eine Lade- und eine Entladefreigabe
(`charg_flag`, `dischrg_flag`); E3DC liefert per RSCP das EMS-Statusbitfeld mit Lade-/Entladesperre
und Sperrzeiten sowie im Systemstatus „Notstromreserve erreicht".

## Entscheidung

- Beide Adapter lesen den Gerätestatus im `read()` mit, höchstens alle `STATUS_POLL_INTERVAL`
  (15 s), und tragen ihn als optionale Felder in `StorageState` ein. `None` heißt „keine Angabe",
  nie „gesperrt". Scheitert nur die Statusabfrage, bleibt der Poll gültig.
- Neuer Sensor `hems_schnittstelle` (nur mit HEMS-Präfix), vom User so festgelegt: **ein** Sensor
  mit allen Informationen zwischen HEMS und Provider als Attribute. State ist der Betriebszustand
  (`bereit`, `laden_gesperrt`, `entladen_gesperrt`, `gesperrt`, `getrennt`). Attribute: Messwerte,
  Freigaben, Sperrgründe und der Spiegel dessen, was die Anbindung aus den HEMS-Helfern liest und
  sendet. Der Sensor ist immer verfügbar, damit `getrennt` sichtbar und für das HEMS lesbar ist.
- HEMS → Provider bleibt bei den bestehenden Helfern; der Sensor spiegelt sie nur.
- Leistungs-, Anforderungs- und Zeitwerte stehen in `_unrecorded_attributes`: jede Änderung
  schriebe sonst den gesamten Attributsatz in den Recorder. Ihr Verlauf liegt in den
  Einzel-Sensoren, die unverändert bleiben.
- Schnittstelle verbindlich im Vertrag HEMS ↔ Battery-Provider 1.2, Abschnitt
  „Schnittstellen-Sensor". SkytechHEMS liest den Sensor über sein Feld `provider_entity`
  (dort D-068).

## Verworfen

- Je Freigabe ein eigener `binary_sensor`: im HEMS zwei weitere Konfigurationsfelder je Speicher,
  und die Zusammengehörigkeit von Messwert und Freigabe ginge verloren.
- Sperre aus „Soll gesendet, Ist bleibt 0" ableiten: erkennt die Folge, nicht die Ursache, und
  bräuchte eine geratene Wartezeit.

## Folgen

- Eine zusätzliche Geräteabfrage je 15 s (Marstek: eine UDP-Anfrage, E3DC: zwei RSCP-Anfragen).
- Ob `dischrg_flag` die beobachtete Verweigerung tatsächlich meldet und ob die E3DC-Bitbelegung
  per RSCP der Modbus-Doku entspricht, ist an Hardware zu bestätigen
  ([bekannte-luecken.md](../bekannte-luecken.md#gerätefreigaben--an-hardware-zu-bestätigen-d-017)).
  Bis dahin soll das HEMS die Freigaben nicht auswerten.
