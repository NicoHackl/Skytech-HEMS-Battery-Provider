import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/Layout'
import { useToast } from '../components/Toast'
import { formatZeitpunkt } from '../format'
import type { Eintrag } from '../types'

/* Referenz für jede Listenseite: Ladezustand (rows === null), Leerzustand mit
   Primäraktion, gefüllte Tabelle. Zeilenaktionen sperren nur ihre eigene Zeile.
   Angezeigt wird nur, was den Nutzer betrifft: der Zeitstempel läuft durch
   format.ts, die ID bleibt unsichtbar und dient nur als React-Key. */

export function Eintraege() {
  const [rows, setRows] = useState<Eintrag[] | null>(null)
  const [busy, setBusy] = useState<number | null>(null)
  const { toast } = useToast()

  const load = useCallback(
    () => api.eintraege().then(setRows).catch((err: Error) => toast(err.message, 'err')),
    [toast],
  )
  useEffect(() => { void load() }, [load])

  async function action(id: number, work: () => Promise<unknown>, message?: string) {
    setBusy(id)
    try {
      await work()
      if (message) toast(message)
      await load()
    } catch (err) {
      toast((err as Error).message, 'err')
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <PageHeader
        title="Einträge"
        subtitle="Bestand verwalten"
        actions={<button className="btn btn-primary"><Icon name="plus" size={16} />Neuer Eintrag</button>}
      />
      <div className="content">
        {rows === null ? (
          <div className="center"><div className="spinner" /></div>
        ) : rows.length === 0 ? (
          <div className="card">
            <div className="empty">
              <Icon name="list" size={40} />
              <p>Noch keine Einträge angelegt.</p>
              <button className="btn btn-primary"><Icon name="plus" size={16} />Ersten Eintrag anlegen</button>
            </div>
          </div>
        ) : (
          <div className="card">
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr><th>Titel</th><th>Status</th><th>Geändert</th><th /></tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id}>
                      <td className="cell-title">{row.title}</td>
                      <td>
                        {row.active
                          ? <span className="pill ok">Aktiv</span>
                          : <span className="pill muted">Inaktiv</span>}
                      </td>
                      <td className="muted">{formatZeitpunkt(row.updated_at)}</td>
                      <td>
                        <div className="row-actions">
                          <button className="icon-btn" title="Bearbeiten" aria-label="Bearbeiten"><Icon name="edit" size={16} /></button>
                          <button
                            className="icon-btn danger-icon"
                            title="Löschen"
                            aria-label="Löschen"
                            disabled={busy === row.id}
                            onClick={() => {
                              if (window.confirm(`„${row.title}“ wirklich löschen?`)) {
                                void action(row.id, () => api.deleteEintrag(row.id), 'Eintrag gelöscht.')
                              }
                            }}
                          >
                            <Icon name="trash" size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
