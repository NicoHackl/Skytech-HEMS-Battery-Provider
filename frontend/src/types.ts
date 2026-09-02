/* Datenverträge zum Backend. Spiegeln die Antworten aus docs/api-referenz.md
   wider — weicht der Server ab, wird hier nachgezogen, nicht mit `any` umgangen. */

export interface Eintrag {
  id: number
  title: string
  active: boolean
  updated_at: string | null
}

/** Was beim Anlegen/Ändern gesendet wird — ohne servergenerierte Felder. */
export interface EintragInput {
  title: string
  active: boolean
}
