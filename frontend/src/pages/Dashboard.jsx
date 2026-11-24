import { useEffect, useState } from 'react'
import {
  createLogement,
  formatFcfa,
  getLogements,
  getReferentiels,
  getReservations,
  getStatus,
  getSynthese,
  updateLogement,
} from '../api.js'

const formulaireVide = {
  nom: '',
  type: 'studio',
  pays: '',
  ville: '',
}

function messageErreur(error) {
  const details = error.details
  if (!details || typeof details !== 'object') {
    return 'Enregistrement impossible.'
  }
  const textes = Object.values(details)
    .flat()
    .filter((valeur) => typeof valeur === 'string')
  return textes[0] || 'Enregistrement impossible.'
}

export default function Dashboard() {
  const [connexion, setConnexion] = useState('Connexion au serveur…')
  const [logements, setLogements] = useState([])
  const [types, setTypes] = useState([])
  const [pays, setPays] = useState([])
  const [filtrePays, setFiltrePays] = useState('')
  const [formulaire, setFormulaire] = useState(null)
  const [erreur, setErreur] = useState('')
  const [enregistrement, setEnregistrement] = useState(false)
  const [reservations, setReservations] = useState([])
  const [synthese, setSynthese] = useState(null)

  async function chargerLogements() {
    setLogements(await getLogements())
  }

  useEffect(() => {
    let cancelled = false

    getStatus()
      .then((data) => {
        if (!cancelled) {
          setConnexion(`Connexion établie : ${JSON.stringify(data)}`)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setConnexion('Connexion impossible.')
        }
      })

    getReferentiels()
      .then((data) => {
        if (!cancelled) {
          setTypes(data.types)
          setPays(data.pays)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setErreur('La liste des pays est indisponible.')
        }
      })

    chargerLogements().catch(() => {
      if (!cancelled) {
        setErreur('Les logements sont indisponibles.')
      }
    })
    getReservations()
      .then((data) => {
        if (!cancelled) {
          setReservations(data)
        }
      })
      .catch(() => {})
    getSynthese()
      .then((data) => {
        if (!cancelled) {
          setSynthese(data)
        }
      })
      .catch(() => {})

    return () => {
      cancelled = true
    }
  }, [])

  function modifierChamp(evenement) {
    const { name, value } = evenement.target
    setFormulaire((actuel) => ({ ...actuel, [name]: value }))
  }

  function ouvrirCreation() {
    setErreur('')
    setFormulaire({ ...formulaireVide })
  }

  function ouvrirModification(logement) {
    setErreur('')
    setFormulaire({
      id: logement.id,
      nom: logement.nom,
      type: logement.type,
      pays: logement.pays,
      ville: logement.ville,
    })
  }

  async function enregistrer(evenement) {
    evenement.preventDefault()
    if (!formulaire.nom.trim() || !formulaire.type) {
      setErreur('Indiquez le nom et le type du logement.')
      return
    }
    if (!formulaire.id && (!formulaire.pays || !formulaire.ville.trim())) {
      setErreur('Indiquez le nom, le type, le pays et la ville.')
      return
    }

    setEnregistrement(true)
    setErreur('')
    const payload = {
      nom: formulaire.nom,
      type: formulaire.type,
      pays: formulaire.pays,
      ville: formulaire.ville,
    }
    try {
      if (formulaire.id) {
        await updateLogement(formulaire.id, payload)
      } else {
        await createLogement(payload)
      }
      await chargerLogements()
      setFormulaire(null)
    } catch (error) {
      setErreur(messageErreur(error))
    } finally {
      setEnregistrement(false)
    }
  }

  const paysPresents = pays.filter((item) =>
    logements.some((logement) => logement.pays === item.code),
  )
  const logementsFiltres = filtrePays
    ? logements.filter((logement) => logement.pays === filtrePays)
    : logements
  const aujourdHui = new Date().toISOString().slice(0, 10)
  const prochains = reservations
    .filter((reservation) => reservation.date_depart >= aujourdHui)
    .slice(0, 3)

  return (
    <section className="page">
      <h1>Tableau de bord</h1>
      <p className="status" role="status">{connexion}</p>

      <div className="barre-logements">
        <h2>Logements</h2>
        {formulaire ? null : (
          <button type="button" className="bouton" onClick={ouvrirCreation}>
            Ajouter un logement
          </button>
        )}
      </div>

      {formulaire ? (
        <form className="formulaire" onSubmit={enregistrer}>
          <h2>{formulaire.id ? 'Modifier le logement' : 'Nouveau logement'}</h2>
          <label>
            Nom
            <input
              name="nom"
              value={formulaire.nom}
              onChange={modifierChamp}
              autoComplete="off"
              required
            />
          </label>
          <label>
            Type
            <select name="type" value={formulaire.type} onChange={modifierChamp} required>
              {types.map((type) => (
                <option key={type.valeur} value={type.valeur}>
                  {type.libelle}
                </option>
              ))}
            </select>
          </label>
          <label>
            Pays
            <select
              name="pays"
              value={formulaire.pays}
              onChange={modifierChamp}
              required={!formulaire.id}
            >
              <option value="">Choisir un pays</option>
              {pays.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.libelle}
                </option>
              ))}
            </select>
          </label>
          <label>
            Ville
            <input
              name="ville"
              value={formulaire.ville}
              onChange={modifierChamp}
              autoComplete="address-level2"
              required={!formulaire.id}
            />
          </label>
          {erreur ? <p className="erreur">{erreur}</p> : null}
          <div className="actions">
            <button type="submit" className="bouton" disabled={enregistrement}>
              Enregistrer
            </button>
            <button
              type="button"
              className="bouton bouton-secondaire"
              onClick={() => setFormulaire(null)}
            >
              Annuler
            </button>
          </div>
        </form>
      ) : null}

      {!formulaire && erreur ? <p className="erreur">{erreur}</p> : null}

      <label className="filtre">
        Pays
        <select value={filtrePays} onChange={(evenement) => setFiltrePays(evenement.target.value)}>
          <option value="">Tous les pays</option>
          {paysPresents.map((item) => (
            <option key={item.code} value={item.code}>
              {item.libelle}
            </option>
          ))}
        </select>
      </label>

      {logementsFiltres.length === 0 ? (
        <p className="vide">
          {logements.length === 0
            ? 'Aucun logement pour le moment.'
            : 'Aucun logement dans ce pays.'}
        </p>
      ) : (
        <ul className="cartes">
          {logementsFiltres.map((logement) => (
            <li key={logement.id} className="carte">
              <h3>{logement.nom}</h3>
              <p>{logement.type_libelle}</p>
              <p>
                {logement.localisation_a_completer
                  ? 'Localisation à compléter'
                  : `${logement.ville}, ${logement.pays_libelle}`}
              </p>
              <button type="button" className="bouton bouton-secondaire" onClick={() => ouvrirModification(logement)}>
                Modifier
              </button>
            </li>
          ))}
        </ul>
      )}

      {synthese ? (
        <div className="montants">
          <p className="montant"><span>À recevoir</span>{formatFcfa(synthese.reste_a_recevoir)}</p>
          <p className="montant"><span>Encaissé</span>{formatFcfa(synthese.montant_encaisse)}</p>
          <p className="montant"><span>Dépenses</span>{formatFcfa(synthese.depenses)}</p>
        </div>
      ) : null}

      <h2 className="sous-titre">Prochains séjours</h2>
      {prochains.length === 0 ? (
        <p className="vide">Aucune arrivée prévue.</p>
      ) : (
        <ul className="cartes">
          {prochains.map((reservation) => (
            <li key={reservation.id} className="carte">
              <h3>{reservation.client_nom}</h3>
              <p>{reservation.logement_nom}</p>
              <p>{reservation.date_arrivee} → {reservation.date_depart}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
