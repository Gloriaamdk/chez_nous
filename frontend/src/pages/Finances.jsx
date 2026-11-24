import { useEffect, useState } from 'react'
import {
  createDepense,
  createPaiement,
  formatFcfa,
  getDepenses,
  getLogements,
  getReferentiels,
  getReservations,
  getSynthese,
} from '../api.js'

const aujourdHui = () => new Date().toISOString().slice(0, 10)

function messageErreur(error) {
  const details = error.details
  if (!details || typeof details !== 'object') {
    return 'Enregistrement impossible.'
  }
  const textes = Object.values(details).flat().filter((valeur) => typeof valeur === 'string')
  return textes[0] || 'Enregistrement impossible.'
}

export default function Finances() {
  const [synthese, setSynthese] = useState(null)
  const [reservations, setReservations] = useState([])
  const [logements, setLogements] = useState([])
  const [depenses, setDepenses] = useState([])
  const [natures, setNatures] = useState([])
  const [paiement, setPaiement] = useState(null)
  const [depense, setDepense] = useState(null)
  const [erreur, setErreur] = useState('')

  async function charger() {
    const [bilan, sejours, biens, sorties, referentiels] = await Promise.all([
      getSynthese(),
      getReservations(),
      getLogements(),
      getDepenses(),
      getReferentiels(),
    ])
    setSynthese(bilan)
    setReservations(sejours)
    setLogements(biens)
    setDepenses(sorties)
    setNatures(referentiels.natures_paiement)
  }

  useEffect(() => {
    charger().catch(() => setErreur('Les montants sont indisponibles.'))
  }, [])

  async function enregistrerPaiement(evenement) {
    evenement.preventDefault()
    setErreur('')
    try {
      await createPaiement({
        reservation: paiement.reservation,
        montant: Number(paiement.montant),
        date: paiement.date,
        nature: paiement.nature,
      })
      setPaiement(null)
      await charger()
    } catch (error) {
      setErreur(messageErreur(error))
    }
  }

  async function enregistrerDepense(evenement) {
    evenement.preventDefault()
    setErreur('')
    try {
      await createDepense({
        logement: depense.logement,
        libelle: depense.libelle,
        montant: Number(depense.montant),
        date: depense.date,
      })
      setDepense(null)
      await charger()
    } catch (error) {
      setErreur(messageErreur(error))
    }
  }

  return (
    <section className="page">
      <h1>Finances</h1>
      {synthese ? (
        <div className="montants">
          <p className="montant"><span>Prévu</span>{formatFcfa(synthese.montant_prevu)}</p>
          <p className="montant"><span>Encaissé</span>{formatFcfa(synthese.montant_encaisse)}</p>
          <p className="montant"><span>Reste à recevoir</span>{formatFcfa(synthese.reste_a_recevoir)}</p>
          <p className="montant"><span>Dépenses</span>{formatFcfa(synthese.depenses)}</p>
        </div>
      ) : null}
      {erreur ? <p className="erreur">{erreur}</p> : null}
      <div className="actions actions-haut">
        <button
          type="button"
          className="bouton"
          onClick={() => setPaiement({
            reservation: reservations[0]?.id || '',
            montant: '',
            date: aujourdHui(),
            nature: 'echeance',
          })}
        >
          Encaisser
        </button>
        <button
          type="button"
          className="bouton bouton-secondaire"
          onClick={() => setDepense({
            logement: logements[0]?.id || '',
            libelle: '',
            montant: '',
            date: aujourdHui(),
          })}
        >
          Dépense
        </button>
      </div>
      {paiement ? (
        <form className="formulaire" onSubmit={enregistrerPaiement}>
          <h2>Encaissement</h2>
          <label>
            Réservation
            <select value={paiement.reservation} onChange={(evenement) => setPaiement({ ...paiement, reservation: evenement.target.value })} required>
              <option value="">Choisir</option>
              {reservations.map((reservation) => (
                <option key={reservation.id} value={reservation.id}>
                  {reservation.client_nom} — {reservation.logement_nom}
                </option>
              ))}
            </select>
          </label>
          <label>
            Montant encaissé (FCFA)
            <input type="number" min="1" step="1" value={paiement.montant} onChange={(evenement) => setPaiement({ ...paiement, montant: evenement.target.value })} required />
          </label>
          <label>
            Date
            <input type="date" value={paiement.date} onChange={(evenement) => setPaiement({ ...paiement, date: evenement.target.value })} required />
          </label>
          <label>
            Nature
            <select value={paiement.nature} onChange={(evenement) => setPaiement({ ...paiement, nature: evenement.target.value })}>
              {natures.map((nature) => (
                <option key={nature.valeur} value={nature.valeur}>{nature.libelle}</option>
              ))}
            </select>
          </label>
          <button type="submit" className="bouton">Enregistrer</button>
        </form>
      ) : null}
      {depense ? (
        <form className="formulaire" onSubmit={enregistrerDepense}>
          <h2>Dépense</h2>
          <label>
            Logement
            <select value={depense.logement} onChange={(evenement) => setDepense({ ...depense, logement: evenement.target.value })} required>
              <option value="">Choisir</option>
              {logements.map((logement) => (
                <option key={logement.id} value={logement.id}>{logement.nom}</option>
              ))}
            </select>
          </label>
          <label>
            Libellé
            <input value={depense.libelle} onChange={(evenement) => setDepense({ ...depense, libelle: evenement.target.value })} required />
          </label>
          <label>
            Montant (FCFA)
            <input type="number" min="1" step="1" value={depense.montant} onChange={(evenement) => setDepense({ ...depense, montant: evenement.target.value })} required />
          </label>
          <label>
            Date
            <input type="date" value={depense.date} onChange={(evenement) => setDepense({ ...depense, date: evenement.target.value })} required />
          </label>
          <button type="submit" className="bouton">Enregistrer</button>
        </form>
      ) : null}
      <h2 className="sous-titre">Séjours</h2>
      {reservations.length === 0 ? <p className="vide">Aucun encaissement à suivre.</p> : (
        <ul className="cartes">
          {reservations.map((reservation) => (
            <li key={reservation.id} className="carte">
              <h3>{reservation.client_nom}</h3>
              <p>{reservation.logement_nom}</p>
              <p>Prévu {formatFcfa(reservation.montant_total_prevu)}</p>
              <p>Encaissé {formatFcfa(reservation.montant_encaisse)}</p>
              <p>Reste {formatFcfa(reservation.reste_a_recevoir)}</p>
            </li>
          ))}
        </ul>
      )}
      <h2 className="sous-titre">Dépenses</h2>
      {depenses.length === 0 ? <p className="vide">Aucune dépense.</p> : (
        <ul className="cartes">
          {depenses.map((item) => (
            <li key={item.id} className="carte">
              <h3>{item.libelle}</h3>
              <p>{item.logement_nom}</p>
              <p>{formatFcfa(item.montant)} · {item.date}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
