import { useState } from 'react'
import Calendrier from './pages/Calendrier.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Finances from './pages/Finances.jsx'
import Rapports from './pages/Rapports.jsx'
import Reservations from './pages/Reservations.jsx'

const pages = [
  { id: 'dashboard', label: 'Accueil', Component: Dashboard },
  { id: 'calendrier', label: 'Calendrier', Component: Calendrier },
  { id: 'reservations', label: 'Réservations', Component: Reservations },
  { id: 'finances', label: 'Finances', Component: Finances },
  { id: 'rapports', label: 'Rapports', Component: Rapports },
]

export default function App() {
  const [pageId, setPageId] = useState('dashboard')
  const [brouillon, setBrouillon] = useState(null)
  const current = pages.find((page) => page.id === pageId) ?? pages[0]
  const Page = current.Component

  function choisirLogement(choix) {
    setBrouillon(choix)
    setPageId('reservations')
  }

  return (
    <div className="app">
      <p className="brand">Chez Nous</p>
      <Page brouillon={brouillon} onChoisirLogement={choisirLogement} />
      <nav aria-label="Écrans">
        {pages.map((page) => (
          <button
            key={page.id}
            type="button"
            aria-current={page.id === current.id ? 'page' : undefined}
            onClick={() => setPageId(page.id)}
          >
            {page.label}
          </button>
        ))}
      </nav>
    </div>
  )
}
