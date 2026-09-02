# Konfiguration

## Umgebungsvariablen

| Variable | Pflicht | Default | Bedeutung |
|---|---|---|---|
| `<NAME>` | ja | — | <…> |
| `<NAME>` | nein | `<wert>` | <…> |

Vorlage für lokale Werte: `.env.example` (eingecheckt).
Die echte `.env` ist in `.gitignore` und wird **nie** committet.

## Konfigurationsdateien

| Datei | Zweck | Eingecheckt |
|---|---|---|
| `{{VERSIONSDATEI}}` | Version und Metadaten | ja |
| `.env.example` | Vorlage ohne echte Werte | ja |
| `.env` | Lokale Werte, enthält Secrets | **nein** |

## Secrets

- Secrets kommen ausschließlich aus Umgebungsvariablen oder einem Secret-Store — **nie** aus dem
  Code, nie aus einer eingecheckten Datei.
- Ein Secret taucht nie in Logs, Fehlermeldungen, Traces oder Commit-Messages auf.
- Beim Start wird geprüft, ob alle Pflichtwerte gesetzt sind. Fehlt einer, bricht der Start mit
  einer klaren deutschen Meldung ab — kein stiller Fallback auf einen Default.
- Weitergehende Regeln: [sicherheit-datenschutz.md](sicherheit-datenschutz.md).

## Grundsatz

Alles, was sich zwischen Umgebungen unterscheidet (Pfade, Hosts, Zeitintervalle, Grenzwerte), ist
konfigurierbar und hat einen sinnvollen Default. Fest verdrahtete Werte im Code sind ein Fehler,
kein Feature.
