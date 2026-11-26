import { useEffect, useRef, useState } from 'react'
import {
  deconnecter,
  definirGestionnaireSession,
  getMoi,
  preparerCsrf,
} from './api.js'
import {
  Alerte,
  Chargement,
  IconeAccueil,
  IconeArgent,
  IconeLogements,
  IconePlus,
  IconeReservations,
  LogoComplet,
  Marque,
} from './interface.jsx'
import Connexion from './pages/Connexion.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Finances from './pages/Finances.jsx'
import Logements from './pages/Logements.jsx'
import Plus from './pages/Plus.jsx'
import Reservations from './pages/Reservations.jsx'

const onglets = [
  { id: 'accueil', label: 'Accueil', Icone: IconeAccueil },
  { id: 'reservations', label: 'Réservations', Icone: IconeReservations },
  { id: 'logements', label: 'Logements', Icone: IconeLogements },
  { id: 'argent', label: 'Argent', Icone: IconeArgent },
  { id: 'plus', label: 'Plus', Icone: IconePlus },
]

export default function App() {
  const [pageId, setPageId] = useState('accueil')
  const [brouillon, setBrouillon] = useState(null)
  const [intention, setIntention] = useState(null)
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

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pageId])

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
    setPageId('accueil')
    setBrouillon(null)
    setIntention(null)
  }

  function aller(page, prochaine = null) {
    if (prochaine?.action === 'creer') {
      setBrouillon(null)
    }
    setIntention(prochaine)
    setPageId(page)
  }

  function choisirLogement(choix) {
    setIntention(null)
    setBrouillon(choix)
    setPageId('reservations')
  }

  if (chargement) {
    return (
      <div className="ecran-connexion">
        <LogoComplet />
        <Chargement texte="Chargement…" />
      </div>
    )
  }

  if (erreurServeur) {
    return (
      <div className="ecran-connexion">
        <LogoComplet />
        <div className="carte-connexion">
          <Alerte>{erreurServeur}</Alerte>
          <button
            className="bouton bouton-large"
            type="button"
            onClick={() => {
              setChargement(true)
              setEssai((valeur) => valeur + 1)
            }}
          >
            Réessayer
          </button>
        </div>
      </div>
    )
  }

  if (!profil) {
    return (
      <div className="ecran-connexion">
        <LogoComplet />
        <Connexion sessionExpiree={sessionExpiree} onConnectee={connectee} />
      </div>
    )
  }

  let page = null
  if (pageId === 'accueil') {
    page = <Dashboard profil={profil} onAller={aller} />
  } else if (pageId === 'reservations') {
    page = (
      <Reservations
        brouillon={brouillon}
        intention={intention}
      />
    )
  } else if (pageId === 'logements') {
    page = <Logements />
  } else if (pageId === 'argent') {
    page = (
      <Finances
        intention={intention}
      />
    )
  } else {
    page = <Plus onChoisirLogement={choisirLogement} />
  }

  return (
    <div className="app">
      <a className="passer" href="#contenu">Aller au contenu</a>
      <nav className="barre" aria-label="Écrans">
        {onglets.map((onglet) => {
          const Icone = onglet.Icone
          const actif = pageId === onglet.id
          return (
            <button
              key={onglet.id}
              type="button"
              aria-current={actif ? 'page' : undefined}
              onClick={() => {
                setIntention(null)
                setPageId(onglet.id)
              }}
            >
              <Icone />
              <span>{onglet.label}</span>
            </button>
          )
        })}
      </nav>
      <div className="colonne" id="contenu">
        <header className="entete">
          <Marque />
          <button className="bouton-quitter" type="button" onClick={quitter}>
            Se déconnecter
          </button>
        </header>
        {page}
      </div>
    </div>
  )
}
