/* Einziger Ort, an dem aus einem Rohwert ein Anzeigetext wird. Kein Wert aus der
   API geht ungefiltert ins Markup: ein ISO-Zeitstempel, ein `null` oder ein
   NaN auf dem Bildschirm ist ein Fehler (eiserne Regel 12 in AGENTS.md).
   Die Zeitzone steht hier in der Funktion — nie als Zusatz in der Ausgabe. */

const ZONE = 'Europe/Berlin'
/** Was angezeigt wird, wenn kein Wert da ist. Nie "null", "N/A" oder "-1". */
const LEER = '–'

const DATUM = new Intl.DateTimeFormat('de-DE', {
  timeZone: ZONE, day: '2-digit', month: '2-digit', year: 'numeric',
})
const UHRZEIT = new Intl.DateTimeFormat('de-DE', {
  timeZone: ZONE, hour: '2-digit', minute: '2-digit',
})

function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null
  const wert = new Date(iso)
  return Number.isNaN(wert.getTime()) ? null : wert
}

/** `15.08.2026` */
export function formatDatum(iso: string | null | undefined): string {
  const wert = parse(iso)
  return wert ? DATUM.format(wert) : LEER
}

/** `21:03` — ohne Zonenkürzel, das interessiert niemanden. */
export function formatUhrzeit(iso: string | null | undefined): string {
  const wert = parse(iso)
  return wert ? UHRZEIT.format(wert) : LEER
}

/** `15.08.2026, 21:03` */
export function formatZeitpunkt(iso: string | null | undefined): string {
  const wert = parse(iso)
  return wert ? `${DATUM.format(wert)}, ${UHRZEIT.format(wert)}` : LEER
}

/** Deutsche Schreibweise, mit der Genauigkeit der Quelle — nicht mehr. */
export function formatZahl(wert: number | null | undefined, nachkomma = 0): string {
  if (typeof wert !== 'number' || !Number.isFinite(wert)) return LEER
  return new Intl.NumberFormat('de-DE', {
    minimumFractionDigits: nachkomma,
    maximumFractionDigits: nachkomma,
  }).format(wert)
}

/** Zahl mit Einheit: `30 s`, `21,5 °C`. Einheit gehört an den Wert, nicht ins Label. */
export function formatMenge(
  wert: number | null | undefined,
  einheit: string,
  nachkomma = 0,
): string {
  const zahl = formatZahl(wert, nachkomma)
  return zahl === LEER ? LEER : `${zahl} ${einheit}`
}
