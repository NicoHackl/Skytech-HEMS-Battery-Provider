import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/Layout'

/* Einstiegsseite: Begrüßungskarte plus Kachelraster als Einsprung in die
   Bereiche. Zahlen kommen aus einem Sammelaufruf; scheitert er, bleibt die
   Kachel stehen und zeigt „–“ statt zu verschwinden. */

export function Dashboard() {
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    api.eintraege()
      .then((rows) => { if (!cancelled) setCounts({ eintraege: rows.length }) })
      .catch((err: Error) => { if (!cancelled) setError(err.message) })
    return () => { cancelled = true }
  }, [])

  return (
    <>
      <PageHeader title="Übersicht" subtitle="Inhalte verwalten" />
      <div className="content">
        {error ? <div className="alert">{error}</div> : null}

        <div className="welcome-card card">
          <div className="card-body">
            <div className="welcome-icon"><Icon name="dashboard" size={21} /></div>
            <div>
              <h2>{'{{PROJEKT_NAME}}'}</h2>
              <p className="muted">Bereich wählen, um Inhalte zu bearbeiten.</p>
            </div>
          </div>
        </div>

        <div className="tiles dashboard-tiles">
          <Link to="/eintraege" className="tile">
            <div className="tile-icon"><Icon name="list" size={20} /></div>
            <h3>Einträge</h3>
            <div className="num">{counts.eintraege ?? '–'}</div>
            <p>Bestand verwalten</p>
          </Link>
        </div>
      </div>
    </>
  )
}
