# Frontend — Architektur und Muster

> Gilt für jede Web-Oberfläche des Projekts. Das **Aussehen** (Tokens, Klassen, Zustände) steht in
> [design-system.md](design-system.md), der **Inhalt der Texte** in
> [nutzertexte.md](nutzertexte.md). Beides wird hier nicht wiederholt — hier steht, wie der Code
> aufgebaut ist.

Vorbild und Referenz sind die Admin-Oberflächen von `FCR_CMS` und
`FCR-Digitale-Stadion-Zeitung`. Wer hier abweicht, begründet es in
[design-entscheidungen.md](design-entscheidungen.md) — nicht im Code.

## Stack — festgelegt

| Baustein | Wahl | Warum |
|---|---|---|
| Bibliothek | React 18 | Bekannt, stabil, kein Framework-Overhead |
| Sprache | TypeScript, `strict: true` | Fehler zur Bauzeit statt im Betrieb |
| Bündler | Vite | Schneller Dev-Server, eingebauter Proxy |
| Routing | `react-router-dom` | Einzige Laufzeit-Abhängigkeit neben React |
| Styling | eine `styles.css` | siehe [design-system.md](design-system.md) |
| Zustand | React-Bordmittel (`useState`, Context) | Oberflächen dieser Größe brauchen keinen Store |
| Datenabruf | `fetch` in einem eigenen Modul | Ein typisierter Client ist kürzer als die Konfiguration einer Library |

**Nicht** verwendet und ohne ausdrückliche Entscheidung auch nicht einzuführen: Redux, Zustand,
MobX, React Query, SWR, Axios, Formik, React Hook Form, Tailwind, MUI, shadcn, Icon-Pakete.
Jede dieser Abhängigkeiten kostet mehr Wartung, als sie in einer Oberfläche mit 5–15 Seiten spart.

Neue Laufzeit-Abhängigkeit = Design-Entscheidung, siehe
[entwicklerrichtlinien.md](entwicklerrichtlinien.md).

## Verzeichnisstruktur

```text
{{FRONTEND_ORDNER}}/
├── index.html              # nur die Hülle: #root + Modul-Script
├── package.json
├── tsconfig.json
├── vite.config.ts
└── src/
    ├── main.tsx            # Einstieg: Router + Provider + styles.css
    ├── App.tsx             # ausschliesslich die Routentabelle
    ├── styles.css          # das gesamte Design-System
    ├── api.ts              # typisierter API-Client (einziger fetch-Ort)
    ├── types.ts            # Datenverträge zum Backend
    ├── format.ts           # Rohwert → Anzeigetext (einziger Ort dafür)
    ├── components/         # wiederverwendbar: Layout, Theme, Toast, Icon, …
    └── pages/              # eine Datei je Route
```

Regel: `pages/` kennt `components/`, nie umgekehrt. Wächst eine Seite über ~150 Zeilen, wandert
der wiederverwendbare Teil nach `components/`.

Wird der Client in mehreren Anwendungen gebraucht (Frontend **und** Server), liegt das Datenmodell
in einem gemeinsamen Ordner (`shared/`) und wird per Pfad-Alias eingebunden — siehe
[architektur.md](architektur.md).

## Einstieg und Provider

`main.tsx` verdrahtet nur; es enthält keine Logik. Reihenfolge der Provider ist verbindlich:
Router außen, dann Theme, dann Toast, dann Auth — Theme hängt an nichts und alles darunter darf es
lesen, Auth meldet Fehler über Toasts und kann deshalb nicht über dem Toast-Provider liegen.

```tsx
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>          {/* basename setzen, wenn die SPA unter /admin liegt */}
      <ThemeProvider>        {/* Pflicht — siehe „Hell und Dunkel" */}
        <ToastProvider>
          <AuthProvider>     {/* entfällt bei Anwendungen ohne Anmeldung */}
            <App />
          </AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
)
```

## Hell und Dunkel

Der Schalter ist Pflicht — eiserne Regel 11 in [`../AGENTS.md`](../AGENTS.md). Die Farbwerte dazu
stehen in [design-system.md](design-system.md), hier steht nur die Mechanik.

`components/Theme.tsx` liefert drei Dinge und **keine einzige Farbe**:

| Export | Aufgabe |
|---|---|
| `ThemeProvider` | Setzt `data-theme` am `<html>`, speichert die Wahl in `localStorage`, folgt der Systemvorgabe nur so lange, wie der Nutzer nicht selbst gewählt hat |
| `useTheme()` | `{ theme, setTheme, toggleTheme }`; wirft außerhalb des Providers einen verständlichen Fehler |
| `ThemeSwitch` | Der Knopf selbst, `.icon-btn` mit `aria-pressed` und `aria-label` |

Verbindlich daran:

- `ThemeSwitch` sitzt in `PageHeader`, nicht in der Sidebar — die fährt unter 820px aus dem Bild,
  der Schalter muss aber auf jeder Seite erreichbar bleiben.
- `index.html` trägt ein kurzes Inline-Skript im `<head>`, das `data-theme` **vor** dem ersten
  Frame setzt. Ohne das blitzt die helle Oberfläche auf, bevor React geladen ist.
- Der Provider schreibt ausschließlich das Attribut. Wer im TSX auf `theme === 'dark'` verzweigt,
  um eine Farbe zu wählen, hat das System umgangen — die Verzweigung gehört in `styles.css`.
- Ein Icon oder Bild, das nur in einem Modus lesbar ist, wird über `currentColor` gelöst, nicht
  über zwei Dateien.

## Routing

`App.tsx` enthält **nur** die Routentabelle, keinen Zustand und kein Markup außer der
Fallback-Route. Das Layout ist eine Elternroute mit `<Outlet />`, damit Sidebar und Kopfzeile beim
Seitenwechsel nicht neu montiert werden.

```tsx
<Routes>
  <Route path="/login" element={<Login />} />
  <Route element={<Protected><Layout /></Protected>}>
    <Route path="/" element={<Dashboard />} />
    <Route path="/slides" element={<Slides />} />
    <Route path="/slides/new" element={<SlideEdit mode="create" />} />
    <Route path="/slides/:id" element={<SlideEdit mode="edit" />} />
    <Route path="*" element={<div className="content"><div className="empty">Seite nicht gefunden.</div></div>} />
  </Route>
</Routes>
```

Muster je Datentyp: **Liste** (`/x`), **Anlegen** (`/x/new`), **Bearbeiten** (`/x/:id`). Anlegen
und Bearbeiten teilen sich eine Komponente mit `mode: 'create' | 'edit'` — zwei fast gleiche
Formulare laufen garantiert auseinander.

Zugriffsschutz sind kleine Wrapper-Komponenten (`Protected`, `AdminOnly`), die auf `<Navigate>`
umleiten. Der Server prüft trotzdem eigenständig; die Frontend-Prüfung ist Bequemlichkeit, keine
Sicherheit — siehe [sicherheit-datenschutz.md](sicherheit-datenschutz.md).

## API-Client

Genau **ein** Modul ruft `fetch` auf. Keine Seite und keine Komponente ruft direkt `fetch` — sonst
liegen Basis-Pfad, Header, Token und Fehlerbehandlung verstreut im Code.

Aufbau:

```ts
export class ApiError extends Error {
  constructor(message: string, public status: number, public details?: unknown) { super(message) }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  // Token, falls vorhanden: headers.set('Authorization', `Bearer ${token}`)
  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...options, headers })
  } catch (err) {
    // „Failed to fetch“ ist englisch und technisch — Ursache ins Log, Satz nach oben.
    console.error('Netzwerkfehler', path, err)
    throw new ApiError('Der Server ist gerade nicht erreichbar. Bitte später erneut versuchen.', 0)
  }
  const isJson = response.headers.get('content-type')?.includes('application/json')
  const body = isJson ? await response.json() : await response.text()
  if (!response.ok) {
    const detail = isJson ? (body as { detail?: unknown }).detail : body
    // Statuscode bleibt am Fehlerobjekt, nicht im Text: Regel 12.
    const message = typeof detail === 'string' ? detail : 'Die Anfrage hat nicht geklappt. Bitte erneut versuchen.'
    throw new ApiError(message, response.status, detail)
  }
  return body as T
}

export const api = {
  slides: () => request<Slide[]>('/slides'),
  createSlide: (data: SlideInput) => request<{ id: number }>('/slides', { method: 'POST', body: JSON.stringify(data) }),
  deleteSlide: (id: number) => request<{ success: boolean }>(`/slides/${id}`, { method: 'DELETE' }),
}
```

Verbindlich daran:

- `Content-Type` wird bei `FormData` **nicht** gesetzt — sonst fehlt die Multipart-Boundary und der
  Upload schlägt fehl.
- Jeder Aufruf ist ein benannter Eintrag im `api`-Objekt, kein roher Pfad in der Seite.
- Rückgabetypen kommen aus `types.ts` und spiegeln den Vertrag aus
  [api-referenz.md](api-referenz.md).
- Fehlertexte sind deutsch, benennen die Ursache aus Nutzersicht und enthalten **keinen
  Statuscode und keinen Klassennamen** (eiserne Regel 12). `ApiError` trägt `status` und `details`
  weiterhin — für die Zuordnung von Feldfehlern und fürs Log, nicht für den Bildschirm.
- Ein fehlgeschlagener `fetch` (kein Netz, Server aus) wird abgefangen und übersetzt. Der
  Browsertext „Failed to fetch" ist englisch und technisch und landet nie in einem Toast.
- `401` wird zentral behandelt: Token verwerfen und ein Ereignis feuern, auf das der
  `AuthProvider` mit Abmelden reagiert. Nicht in jeder Seite einzeln.

## Anzeigewerte: `format.ts`

Kein Rohwert aus der API geht direkt ins Markup. `{row.updated_at}` rendert einen ISO-Zeitstempel
mit `T` und `Z` — genau das, was eiserne Regel 12 verbietet. Zwischen Datenvertrag und Anzeige
liegt deshalb **ein** Modul:

```ts
const ZONE = 'Europe/Berlin'
const DATUM = new Intl.DateTimeFormat('de-DE', { timeZone: ZONE, day: '2-digit', month: '2-digit', year: 'numeric' })
const UHRZEIT = new Intl.DateTimeFormat('de-DE', { timeZone: ZONE, hour: '2-digit', minute: '2-digit' })

function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d
}

/** `15.08.2026, 21:03` — ohne Zonenzusatz, den liest niemand. */
export function formatZeitpunkt(iso: string | null | undefined): string {
  const d = parse(iso)
  return d ? `${DATUM.format(d)}, ${UHRZEIT.format(d)}` : '–'
}
```

Verbindlich daran:

- `formatDatum`, `formatUhrzeit`, `formatZeitpunkt`, `formatZahl` liegen hier und **nur** hier.
  Ein `toLocaleString`-Aufruf in einer Seite ist ein Fehler — er läuft irgendwann auseinander.
- `timeZone` steht in der Funktion, nicht in der Ausgabe. Kein `timeZoneName`, kein angehängtes
  „Berliner Zeit".
- Leer- und Fehlwerte werden hier abgefangen und zu `–`. `null`, `undefined`, `NaN` oder
  `Invalid Date` erreichen das Markup nicht.
- Zahlen ebenso: `Intl.NumberFormat('de-DE')` mit der Genauigkeit, die die Quelle hergibt.

## Seitenmuster: Liste

Ladezustand wird über `null` unterschieden, nicht über ein zweites `loading`-Flag — `null` heißt
„noch nicht geladen", `[]` heißt „leer".

```tsx
const [rows, setRows] = useState<Slide[] | null>(null)
const [busy, setBusy] = useState<number | null>(null)
const { toast } = useToast()
const load = useCallback(() => api.slides().then(setRows).catch((err: Error) => toast(err.message, 'err')), [toast])
useEffect(() => { void load() }, [load])
```

Für Aktionen auf einer Zeile eine gemeinsame Hilfsfunktion: Zeile sperren, ausführen, Rückmeldung,
neu laden, entsperren — auch im Fehlerfall (`finally`).

Drei Zustände, immer alle drei umgesetzt:

| Zustand | Darstellung |
|---|---|
| Laden | `<div className="center"><div className="spinner" /></div>` |
| Leer | `.empty` in einer Karte: Icon, ein erklärender Satz, Primäraktion („Erste Folie anlegen") |
| Gefüllt | Tabelle (`table.data`) bei gleichförmigen Daten, Kartenliste bei Datensätzen mit Vorschau oder Sortierung |

Ein Leerzustand ohne Weg zur ersten Aktion ist eine Sackgasse und gilt als Fehler.

## Seitenmuster: Formular

- Ein Zustandsobjekt für den Datensatz, geändert über eine `patch(partial)`-Funktion.
- `saving`-Flag sperrt den Speichern-Button und wechselt seine Beschriftung auf „Speichern…".
- Feldfehler kommen als `Record<string, string>` vom Server, landen in `fieldErrors` und färben
  gezielt das betroffene Feld (`.field.invalid` + `.field-error`). Ein globaler Toast ersetzt keine
  Feldmarkierung.
- Nach dem Speichern: Toast **und** Rücknavigation zur Liste.
- Formularaufbau folgt dem Server-Schema, wo eines existiert: Feldtyp → Widget. Zwei Quellen für
  „welche Felder hat dieser Datensatz" laufen sonst auseinander.
- Zerstörende Aktionen bestätigen mit dem Namen des Objekts:
  `window.confirm('„' + titel + '" wirklich löschen?')`.

## Rückmeldung an den Nutzer

| Mittel | Wofür |
|---|---|
| Toast (`ok` / `err`) | Ergebnis einer Aktion: gespeichert, gelöscht, fehlgeschlagen. Verschwindet nach ~4 s |
| `.alert` | Fehler, der die ganze Seite betrifft und stehen bleiben muss |
| `.field-error` | Fehler an genau einem Eingabefeld |
| `.hint-box` | Fehlende Voraussetzung plus Knopf, der sie herstellt |
| `.info-strip` | Erklärung zur Bedienung einer Liste, kein Fehler |

Der Toast-Provider stellt einen `useToast()`-Hook bereit und wirft außerhalb des Providers einen
verständlichen Fehler statt `undefined` zurückzugeben.

Hier steht nur das **Mittel**. Was darin geschrieben steht — und was gerade nicht, etwa Statuscode
oder Exception-Name — regelt [nutzertexte.md](nutzertexte.md). Ein `catch`, der `err.message`
ungeprüft in einen Toast schiebt, reicht technische Texte an den Nutzer durch.

## Layout

`components/Layout.tsx` liefert zwei Dinge:

1. `Layout` — Sidebar (Marke, Navigationsgruppen mit Zählern, Fußbereich) plus `<main>` mit
   `<Outlet />`. Unter 820px als Off-Canvas-Panel mit Hintergrund-Backdrop.
2. `PageHeader` — die klebrige Kopfzeile jeder Seite: `title`, optional `subtitle`, den
   `ThemeSwitch` und optional `actions` (die Primäraktion der Seite).

Jede Seite rendert `<PageHeader …/>` gefolgt von `<div className="content">`. Keine Seite baut sich
eine eigene Kopfzeile.

Zähler in der Navigation kommen aus einem Sammelaufruf beim Montieren des Layouts; schlägt er fehl,
verschwindet nur der Zähler, nicht die Navigation.

## Konfiguration und Auslieferung

```ts
// vite.config.ts
export default defineConfig({
  base: '/admin/',                       // nur, wenn die SPA nicht unter / liegt
  plugins: [react()],
  server: {
    port: 5174,                          // Port je Anwendung festlegen, nicht raten
    proxy: {                             // Dev: gleiche Origin wie in Produktion, kein CORS
      '/api': { target: 'http://127.0.0.1:{{BACKEND_PORT}}', changeOrigin: true },
      '/media': { target: 'http://127.0.0.1:{{BACKEND_PORT}}', changeOrigin: true },
    },
  },
})
```

- Der Build prüft erst Typen, dann bündelt er: `"build": "tsc --noEmit && vite build"`. Ein Build,
  der Typfehler durchlässt, ist wertlos.
- API-Pfade sind **relativ** (`/api/…`). Keine absolute Basis-URL im Code, keine
  `VITE_API_URL`-Variable — Dev-Proxy und Produktions-Reverse-Proxy erledigen das.
- Auslieferung entweder als statisches Bündel hinter einem Webserver mit SPA-Fallback
  (`try_files $uri $uri/ /index.html`) oder direkt vom Anwendungsserver gemountet. Beides ist in
  [architektur.md](architektur.md) beschrieben.
- `index.html` enthält `lang="de"`, `data-design` am `<html>`, das Theme-Inline-Skript,
  `viewport`, einen sprechenden `<title>`, `<meta name="theme-color">` und bei internen
  Oberflächen `<meta name="robots" content="noindex, nofollow">`.

## Was ein Agent vor dem ersten Commit prüft

1. `tsc --noEmit` läuft fehlerfrei — `any` ist keine Lösung, sondern eine verschobene Fehlermeldung.
2. Kein direkter `fetch` außerhalb von `api.ts`.
3. Keine Literalfarbe und kein gestaltender Inline-Style im TSX.
4. Lade-, Leer- und Fehlerzustand jeder neuen Seite sind umgesetzt.
5. Jeder Button ohne sichtbaren Text hat ein `aria-label`.
6. Die Ansicht ist bei 375px Breite bedienbar.
7. Die Designsprache war geklärt, bevor gebaut wurde — nicht geraten (eiserne Regel 10).
8. Der Theme-Schalter ist erreichbar, und **jede neue Seite wurde in beiden Modi angesehen**.
   Ein Kontrastfehler fällt nur auf, wer hinschaut.
9. Kein Rohwert im Markup: Zeitstempel, Zahlen und Leerwerte laufen durch `format.ts`, keine
   technische ID, kein Statuscode und kein Zonenzusatz ist sichtbar (eiserne Regel 12,
   Prüfliste in [nutzertexte.md](nutzertexte.md)).
