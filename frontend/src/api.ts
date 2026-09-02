import type { Eintrag, EintragInput } from './types'

/* Einziger Ort im Frontend, an dem fetch aufgerufen wird. Basis-Pfad, Header,
   Token und Fehlerbehandlung liegen damit an genau einer Stelle.
   Pfade sind relativ — Dev-Proxy und Reverse-Proxy erledigen den Rest. */

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public details?: unknown,
  ) {
    super(message)
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  // Bei FormData KEIN Content-Type setzen — sonst fehlt die Multipart-Boundary.
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')

  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...options, headers })
  } catch (err) {
    // Netzwerkfehler heißt im Browser „Failed to fetch“ — englisch, technisch,
    // für den Nutzer wertlos. Ursache ins Log, verständlicher Satz nach oben.
    console.error('Netzwerkfehler', path, err)
    throw new ApiError('Der Server ist gerade nicht erreichbar. Bitte später erneut versuchen.', 0)
  }

  const isJson = response.headers.get('content-type')?.includes('application/json')
  const body = isJson ? await response.json() : await response.text()

  if (!response.ok) {
    const detail = isJson ? (body as { detail?: unknown }).detail : body
    // Der Text ist das, was der Nutzer liest: kein Statuscode, kein Klassenname
    // (eiserne Regel 12). Status und Rohantwort bleiben am Fehlerobjekt — für
    // Feldzuordnung und Log, nicht für den Bildschirm.
    const message = typeof detail === 'string' && detail.trim() !== ''
      ? detail
      : 'Das hat gerade nicht geklappt. Bitte erneut versuchen.'
    console.error('API-Fehler', response.status, path, detail)
    throw new ApiError(message, response.status, detail)
  }
  return body as T
}

/* Jeder Endpunkt ist ein benannter Eintrag — kein roher Pfad in einer Seite. */
export const api = {
  eintraege: () => request<Eintrag[]>('/eintraege'),
  eintrag: (id: string) => request<Eintrag>(`/eintraege/${id}`),
  createEintrag: (data: EintragInput) =>
    request<{ id: number }>('/eintraege', { method: 'POST', body: JSON.stringify(data) }),
  updateEintrag: (id: string, data: EintragInput) =>
    request<{ success: boolean }>(`/eintraege/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteEintrag: (id: number) =>
    request<{ success: boolean }>(`/eintraege/${id}`, { method: 'DELETE' }),
}
