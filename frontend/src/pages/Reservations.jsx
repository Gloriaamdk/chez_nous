import { useEffect, useState } from 'react'
import {
  createReservation,
  formatFcfa,
  getLogements,
  getReferentiels,
  getReservations,
} from '../api.js'

const formulaireVide = {
  logement: '',
  client_nom: '',
  client_telephone: '',
  canal: 'whatsapp',
  mode: 'nuitee',
  date_arrivee: '',
  date_depart: '',
  montant_prevu: '',
  acompte: '',
}

function messageErreur(error) {
  const details = error.details
  if (!details || typeof details !== 'object') {
    return 'Enregistrement impossible.'
  }
  if (typeof details.detail === 'string') {
    return details.detail
  }
  const textes = Object.values(details).flat().filter((valeur) => typeof valeur === 'string')
  return textes[0] || 'Enregistrement impossible.'
}

export default function Reservations({ brouillon }) {
  const [logements, setLogements] = useState([])
  const [canaux, setCanaux] = useState([])
  const [modes, setModes] = useState([])
  const [reservations, setReservations] = useState([])
  const [formulaire, setFormulaire] = useState(formulaireVide)
  const [ouvert, setOuvert] = useState(false)
  const [erreur, setErreur] = useState('')
  const [enregistrement, setEnregistrement] = useState(false)

  async function charger() {
    setReservations(await getReservations())
  }

  useEffect(() => {
    getLogements().then(setLogements).catch(() => setErreur('Les logements sont indisponibles.'))
    getReferentiels()
      .then((data) => {
        setCanaux(data.canaux)
        setModes(data.modes)
      })
      .catch(() => setErreur('Les listes de saisie sont indisponibles.'))
    charger().catch(() => setErreur('Les réservations sont indisponibles.'))
  }, [])

  useEffect(() => {
    if (!brouillon) {
      return
    }
    setFormulaire((actuel) => ({
      ...actuel,
      logement: brouillon.logementId,
      date_arrivee: brouillon.arrivee,
      date_depart: brouillon.depart,
    }))
    setOuvert(true)
  }, [brouillon])

  function modifierChamp(evenement) {
    const { name, value } = evenement.target
    setFormulaire((actuel) => ({ ...actuel, [name]: value }))
  }

  async function enregistrer(evenement) {
    evenement.preventDefault()
    setEnregistrement(true)
    setErreur('')
    try {
      await createReservation({
        logement: formulaire.logement,
        client_nom: formulaire.client_nom,
        client_telephone: formulaire.client_telephone,
        canal: formulaire.canal,
        mode: formulaire.mode,
        date_arrivee: formulaire.date_arrivee,
        date_depart: formulaire.date_depart,
        montant_prevu: Number(formulaire.montant_prevu),
        acompte: formulaire.acompte ? Number(formulaire.acompte) : 0,
      })
      await charger()
      setFormulaire(formulaireVide)
      setOuvert(false)
    } catch (error) {
      setErreur(messageErreur(error))
    } finally {
      setEnregistrement(false)
    }
  }

  return (
    <section className="page">
      <div className="barre-logements">
        <h1>Réservations</h1>
        {ouvert ? null : (
          <button type="button" className="bouton" onClick={() => setOuvert(true)}>
            Nouvelle réservation
          </button>
        )}
      </div>
      {brouillon && ouvert ? (
        <p className="intro">Les dates et le logement choisis dans le calendrier sont conservés.</p>
      ) : null}
      {ouvert ? (
        <form className="formulaire" onSubmit={enregistrer}>
          <label>
            Logement
            <select name="logement" value={formulaire.logement} onChange={modifierChamp} required>
              <option value="">Choisir un logement</option>
              {logements.map((logement) => (
                <option key={logement.id} value={logement.id}>{logement.nom}</option>
              ))}
            </select>
          </label>
          <label>
            Arrivée
            <input type="date" name="date_arrivee" value={formulaire.date_arrivee} onChange={modifierChamp} required />
          </label>
          <label>
            Départ
            <input type="date" name="date_depart" value={formulaire.date_depart} onChange={modifierChamp} required />
          </label>
          <label>
            Client
            <input name="client_nom" value={formulaire.client_nom} onChange={modifierChamp} required />
          </label>
          <label>
            Téléphone
            <input name="client_telephone" value={formulaire.client_telephone} onChange={modifierChamp} inputMode="tel" required />
          </label>
          <label>
            Canal
            <select name="canal" value={formulaire.canal} onChange={modifierChamp}>
              {canaux.map((canal) => (
                <option key={canal.valeur} value={canal.valeur}>{canal.libelle}</option>
              ))}
            </select>
          </label>
          <label>
            Séjour
            <select name="mode" value={formulaire.mode} onChange={modifierChamp}>
              {modes.map((mode) => (
                <option key={mode.valeur} value={mode.valeur}>{mode.libelle}</option>
              ))}
            </select>
          </label>
          <label>
            {formulaire.mode === 'mois' ? 'Loyer mensuel (FCFA)' : 'Montant du séjour (FCFA)'}
            <input name="montant_prevu" type="number" min="1" step="1" value={formulaire.montant_prevu} onChange={modifierChamp} required />
          </label>
          <label>
            Acompte encaissé (FCFA)
            <input name="acompte" type="number" min="0" step="1" value={formulaire.acompte} onChange={modifierChamp} />
          </label>
          {erreur ? <p className="erreur">{erreur}</p> : null}
          <div className="actions">
            <button type="submit" className="bouton" disabled={enregistrement}>Enregistrer</button>
            <button type="button" className="bouton bouton-secondaire" onClick={() => setOuvert(false)}>Annuler</button>
          </div>
        </form>
      ) : null}
      {!ouvert && erreur ? <p className="erreur">{erreur}</p> : null}
      {reservations.length === 0 ? (
        <p className="vide">Aucune réservation pour le moment.</p>
      ) : (
        <ul className="cartes">
          {reservations.map((reservation) => (
            <li key={reservation.id} className="carte">
              <h3>{reservation.client_nom}</h3>
              <p>{reservation.logement_nom}</p>
              <p>{reservation.date_arrivee} → {reservation.date_depart}</p>
              <p>{reservation.mode_libelle} · {reservation.canal_libelle}</p>
              <p>Prévu : {formatFcfa(reservation.montant_total_prevu)}</p>
              <p>Encaissé : {formatFcfa(reservation.montant_encaisse)}</p>
              <p>Reste : {formatFcfa(reservation.reste_a_recevoir)}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
