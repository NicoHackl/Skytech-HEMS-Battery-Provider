import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Eintraege } from './pages/Eintraege'

/* Ausschliesslich die Routentabelle. Je Datentyp drei Routen:
   Liste (/x), Anlegen (/x/new), Bearbeiten (/x/:id) — Anlegen und Bearbeiten
   teilen sich eine Komponente mit mode="create" | "edit". */
export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/eintraege" element={<Eintraege />} />
        <Route path="*" element={<div className="content"><div className="empty">Seite nicht gefunden.</div></div>} />
      </Route>
    </Routes>
  )
}
