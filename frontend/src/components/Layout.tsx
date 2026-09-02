import { useState, type ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Icon } from './Icon'
import { ThemeSwitch } from './Theme'

/* App-Gerüst: Sidebar + Hauptspalte. Das Layout ist Elternroute mit <Outlet />,
   damit Navigation und Kopfzeile beim Seitenwechsel nicht neu montiert werden. */

const navClass = ({ isActive }: { isActive: boolean }) => `nav-item${isActive ? ' active' : ''}`

export function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const closeMobile = () => setMobileOpen(false)

  return (
    <div className="shell">
      {mobileOpen ? <button className="sidebar-backdrop" aria-label="Navigation schließen" onClick={closeMobile} /> : null}

      <aside className={`sidebar${mobileOpen ? ' open' : ''}`}>
        <div className="sidebar-brand">
          <span className="crest">{'{{PROJEKT_KUERZEL}}'}</span>
          <div><b>{'{{PROJEKT_NAME}}'}</b><span>Verwaltung</span></div>
        </div>

        <nav className="nav" onClick={closeMobile}>
          <NavLink to="/" end className={navClass}><Icon name="dashboard" /><span>Übersicht</span></NavLink>

          <div className="nav-label">Inhalte</div>
          <NavLink to="/eintraege" className={navClass}><Icon name="list" /><span>Einträge</span></NavLink>
        </nav>

        <div className="sidebar-foot">
          <span className="avatar">–</span>
          <div className="who"><b>{'{{PROJEKT_NAME}}'}</b><span>Lokale Verwaltung</span></div>
          <span className="status-dot" title="Verbindung aktiv" />
        </div>
      </aside>

      <main className="main">
        <button className="mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Navigation öffnen"><Icon name="menu" /></button>
        <Outlet />
      </main>
    </div>
  )
}

/** Klebrige Kopfzeile jeder Seite. Keine Seite baut sich eine eigene.
    Der Theme-Schalter sitzt hier und nicht in der Sidebar: die faehrt unter
    820px aus dem Bild, der Schalter muss aber auf jeder Seite erreichbar sein. */
export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="topbar">
      <div>
        <h1>{title}</h1>
        {subtitle ? <div className="sub">{subtitle}</div> : null}
      </div>
      <div className="spacer" />
      <ThemeSwitch />
      {actions}
    </div>
  )
}
