import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App } from './App'
import { ThemeProvider } from './components/Theme'
import { ToastProvider } from './components/Toast'
import './styles.css'

/* Verdrahtung, keine Logik. Provider-Reihenfolge: Router aussen, dann Theme,
   dann Toast, dann (falls vorhanden) Auth — Theme haengt an nichts und alles
   darunter darf es lesen, Auth meldet Fehler ueber Toasts. */
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
)
