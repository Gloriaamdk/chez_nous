import { useEffect, useRef, useState } from 'react'
import {
  deconnecter,
  definirGestionnaireSession,
  getMoi,
  preparerCsrf,
} from './api.js'
import Calendrier from './pages/Calendrier.jsx'
import Connexion from './pages/Connexion.jsx'
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
  const [profil, setProfil] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [sessionExpiree, setSessionExpiree] = useState(false)
  const [erreurServeur, setErreurServeur] = useState('')
  const [essai, setEssai] = useState(0)
  const profilRef = useRef(null)

  useEffect(() => {
    definirGestionnaireSession(() => {
      if (profilRef.current) {
        profilRef.current = null
        setSessionExpiree(true)
        setProfil(null)
      }
    })
  }, [])

  useEffect(() => {
    let ignore = false

    preparerCsrf()
      .catch(() => null)
      .then(() => getMoi())
      .then((data) => {
        if (ignore) {
          return
        }
        profilRef.current = data
        setProfil(data)
        setErreurServeur('')
        setSessionExpiree(false)
      })
      .catch((error) => {
        if (ignore) {
          return
        }
        profilRef.current = null
        setProfil(null)
        if (error.status === 401) {
          setErreurServeur('')
          return
        }
        setErreurServeur(
          'La connexion au serveur a échoué. Relancez-le, puis réessayez.',
        )
      })
      .finally(() => {
        if (!ignore) {
          setChargement(false)
        }
      })

    return () => {
      ignore = true
    }
  }, [essai])

  function connectee(data) {
    profilRef.current = data
    setSessionExpiree(false)
    setErreurServeur('')
    setProfil(data)
  }

  async function quitter() {
    try {
      await deconnecter()
    } catch {
      // La session est déjà fermée : on revient quand même à l’écran de connexion.
    }
    profilRef.current = null
    setSessionExpiree(false)
    setProfil(null)
    setPageId('dashboard')
    setBrouillon(null)
  }

  if (chargement) {
    return (
      <div className="app app-connexion">
        <p className="brand">Chez Nous</p>
        <main className="page">
          <p className="intro">Chargement…</p>
        </main>
      </div>
    )
  }

  if (erreurServeur) {
    return (
      <div className="app app-connexion">
        <p className="brand">Chez Nous</p>
        <main className="page">
          <h1>Connexion</h1>
          <p className="erreur" role="alert">
            {erreurServeur}
          </p>
          <button
            className="bouton"
            type="button"
            onClick={() => {
              setChargement(true)
              setEssai((valeur) => valeur + 1)
            }}
          >
            Réessayer
          </button>
        </main>
      </div>
    )
  }

  if (!profil) {
    return (
      <div className="app app-connexion">
        <p className="brand">Chez Nous</p>
        <Connexion sessionExpiree={sessionExpiree} onConnectee={connectee} />
      </div>
    )
  }

  const current = pages.find((page) => page.id === pageId) ?? pages[0]
  const Page = current.Component

  function choisirLogement(choix) {
    setBrouillon(choix)
    setPageId('reservations')
  }

  return (
    <div className="app">
      <header className="entete">
        <p className="brand">Chez Nous</p>
        <button className="bouton bouton-secondaire" type="button" onClick={quitter}>
          Se déconnecter
        </button>
      </header>
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
