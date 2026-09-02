# API-Referenz

> Öffentliche Schnittstellen dieses Projekts. Hat das Projekt keine, wird diese Datei gelöscht und
> aus [README.md](README.md) ausgetragen.

## Grundsätzliches

- Basis-URL: `<…>`
- Versionierung: `/api/v1/...` — eine bestehende Hauptversion wird nie brechend geändert.
- Authentifizierung: <…>, siehe [konfiguration.md](konfiguration.md)
- Format: JSON, Zeitangaben als ISO 8601 mit Zeitzone — reines Maschinenformat. Alles, was ein
  Mensch zu sehen bekommt, wird vorher nach Berliner Zeit umgesetzt (Format: eiserne Regel 9 in
  [`AGENTS.md`](../AGENTS.md)) und durchläuft die Formatierung des Clients — ein Feld aus der
  Antwort wird **nie** unverändert angezeigt (eiserne Regel 12,
  [nutzertexte.md](nutzertexte.md)).

## Endpunkte

### `GET /api/v1/<pfad>`

<Was er tut, in einem Satz.>

**Parameter**

| Name | Ort | Typ | Pflicht | Bedeutung |
|---|---|---|---|---|
| <…> | Query/Pfad | <…> | ja/nein | <…> |

**Antwort `200`**

```json
{ "<feld>": "<wert>" }
```

**Fehler**

| Code | Wann | Rumpf |
|---|---|---|
| `400` | Eingabe ungültig | `{"fehler": "<deutscher Text>"}` |
| `404` | Nicht gefunden | `{"fehler": "<deutscher Text>"}` |
| `500` | Interner Fehler | `{"fehler": "<deutscher Text>"}` |

Der Text im Rumpf ist bereits der Satz, den ein Mensch lesen kann: deutsch, ohne Statuscode, ohne
Exception-Namen, ohne Pfad. Die technische Ursache steht im Server-Log, nicht in der Antwort —
sonst reicht der Client sie ungefiltert an den Nutzer durch.

## Fremde Schnittstellen

Von diesem Projekt **genutzte** externe Endpunkte:

| Dienst | Endpunkt | Wofür | Verhalten bei Ausfall |
|---|---|---|---|
| <…> | <…> | <…> | <Fallback — nie „Absturz"> |

Feldbedeutungen nicht hier duplizieren, sondern nach [datenmodell.md](datenmodell.md) verlinken.
