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
import { aujourdhui, formatDate, messageErreur } from '../format.js'
import { Alerte, BadgeCanal, Chargement, Vide } from '../interface.jsx'

export default function Finances({ intention }) {
  const [synthese, setSynthese] = useState(null)
  const [reservations, setReservations] = useState([])
  const [logements, setLogements] = useState([])
  const [depenses, setDepenses] = useState([])
  const [natures, setNatures] = useState([])
  const [paiement, setPaiement] = useState(() => (
    intention?.action === 'encaisser'
      ? { reservation: '', montant: '', date: aujourdhui(), nature: 'echeance' }
      : null
  ))
  const [depense, setDepense] = useState(null)
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(true)
  const [enregistrement, setEnregistrement] = useState(false)

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
    setPaiement((actuel) => {
      if (!actuel || actuel.reservation) {
        return actuel
      }
      const premiere = sejours.find((reservation) => !reservation.annulee)
      return premiere ? { ...actuel, reservation: premiere.id } : actuel
    })
    return sejours
  }

  useEffect(() => {
    let ignore = false
    Promise.all([
      getSynthese(),
      getReservations(),
      getLogements(),
      getDepenses(),
      getReferentiels(),
    ])
      .then(([bilan, sejours, biens, sorties, referentiels]) => {
        if (ignore) {
          return
        }
        setSynthese(bilan)
        setReservations(sejours)
        setLogements(biens)
        setDepenses(sorties)
        setNatures(referentiels.natures_paiement)
        setPaiement((actuel) => {
          if (!actuel || actuel.reservation) {
            return actuel
          }
          const premiere = sejours.find((reservation) => !reservation.annulee)
          return premiere ? { ...actuel, reservation: premiere.id } : actuel
        })
      })
      .catch(() => {
        if (!ignore) {
          setErreur('Les montants sont indisponibles.')
        }
      })
      .finally(() => {
        if (!ignore) {
          setChargement(false)
        }
      })
    return () => {
      ignore = true
    }
  }, [])

  async function enregistrerPaiement(evenement) {
    evenement.preventDefault()
    setErreur('')
    setEnregistrement(true)
    try {
      await createPaiement({
        reservation: paiement.reservation,
        montant: Number(paiement.montant),
        date: paiement.date,
        nature: paiement.nature,
      })
      setPaiement(null)
      window.scrollTo(0, 0)
      await charger()
    } catch (error) {
      setErreur(messageErreur(error))
    } finally {
      setEnregistrement(false)
    }
  }

  async function enregistrerDepense(evenement) {
    evenement.preventDefault()
    setErreur('')
    setEnregistrement(true)
    try {
      await createDepense({
        logement: depense.logement,
        libelle: depense.libelle,
        montant: Number(depense.montant),
        date: depense.date,
      })
      setDepense(null)
      window.scrollTo(0, 0)
      await charger()
    } catch (error) {
      setErreur(messageErreur(error))
    } finally {
      setEnregistrement(false)
    }
  }

  function ouvrirPaiement() {
    setDepense(null)
    setErreur('')
    setPaiement({
      reservation: reservations.find((reservation) => !reservation.annulee)?.id || '',
      montant: '',
      date: aujourdhui(),
      nature: 'echeance',
    })
    window.scrollTo(0, 0)
  }

  function ouvrirDepense() {
    setPaiement(null)
    setErreur('')
    setDepense({
      logement: logements[0]?.id || '',
      libelle: '',
      montant: '',
      date: aujourdhui(),
    })
    window.scrollTo(0, 0)
  }

  const saisie = Boolean(paiement || depense)

  return (
    <section className="page">
      {saisie ? (
        <button
          className="retour"
          type="button"
          onClick={() => {
            setPaiement(null)
            setDepense(null)
            setErreur('')
            window.scrollTo(0, 0)
          }}
        >
          ← Argent
        </button>
      ) : (
        <>
          <h1>Argent</h1>
          <p className="chapo">Le prévu, l’encaissé, le reste, et les dépenses de chaque logement.</p>
        </>
      )}
      {chargement ? <Chargement texte="Chargement des montants…" /> : null}
      {!saisie && synthese ? (
        <ul className="stats">
          <li>
            <span className="stats-valeur stats-montant">{formatFcfa(synthese.montant_prevu)}</span>
            <span className="stats-label">Prévu</span>
          </li>
          <li>
            <span className="stats-valeur stats-montant">{formatFcfa(synthese.montant_encaisse)}</span>
            <span className="stats-label">Encaissé</span>
          </li>
          <li>
            <span className="stats-valeur stats-montant">{formatFcfa(synthese.reste_a_recevoir)}</span>
            <span className="stats-label">À recevoir</span>
          </li>
          <li>
            <span className="stats-valeur stats-montant">{formatFcfa(synthese.depenses)}</span>
            <span className="stats-label">Dépenses</span>
          </li>
        </ul>
      ) : null}
      {!saisie && synthese && synthese.montant_encaisse_annule > 0 ? (
        <p className="note">
          Encaissé sur un séjour annulé : {formatFcfa(synthese.montant_encaisse_annule)}.
          Cette somme ne réduit pas le reste à recevoir des autres séjours.
        </p>
      ) : null}
      {erreur ? <Alerte>{erreur}</Alerte> : null}
      {!saisie ? (
        <div className="actions actions-haut">
          <button type="button" className="bouton" onClick={ouvrirPaiement}>
            Encaisser
          </button>
          <button type="button" className="bouton bouton-secondaire" onClick={ouvrirDepense}>
            Dépense
          </button>
        </div>
      ) : null}
      {paiement ? (
        <form className="formulaire" onSubmit={enregistrerPaiement}>
          <h2>Encaissement</h2>
          <p className="aide">Un encaissement est rattaché à une réservation. Le montant est en FCFA.</p>
          <label>
            Réservation
            <select
              value={paiement.reservation}
              onChange={(evenement) => setPaiement({ ...paiement, reservation: evenement.target.value })}
              required
            >
              <option value="">Choisir</option>
              {reservations.filter((reservation) => !reservation.annulee).map((reservation) => (
                <option key={reservation.id} value={reservation.id}>
                  {reservation.client_nom} — {reservation.logement_nom}
                </option>
              ))}
            </select>
          </label>
          <label>
            Montant encaissé (FCFA)
            <input
              type="number"
              inputMode="numeric"
              min="1"
              step="1"
              value={paiement.montant}
              onChange={(evenement) => setPaiement({ ...paiement, montant: evenement.target.value })}
              required
            />
          </label>
          <label>
            Date
            <input
              type="date"
              value={paiement.date}
              onChange={(evenement) => setPaiement({ ...paiement, date: evenement.target.value })}
              required
            />
          </label>
          <label>
            Nature
            <select
              value={paiement.nature}
              onChange={(evenement) => setPaiement({ ...paiement, nature: evenement.target.value })}
            >
              {natures.map((nature) => (
                <option key={nature.valeur} value={nature.valeur}>{nature.libelle}</option>
              ))}
            </select>
          </label>
          <button type="submit" className="bouton" disabled={enregistrement}>
            {enregistrement ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </form>
      ) : null}
      {depense ? (
        <form className="formulaire" onSubmit={enregistrerDepense}>
          <h2>Dépense</h2>
          <p className="aide">Chaque dépense est rattachée à un logement.</p>
          <label>
            Logement
            <select
              value={depense.logement}
              onChange={(evenement) => setDepense({ ...depense, logement: evenement.target.value })}
              required
            >
              <option value="">Choisir</option>
              {logements.map((logement) => (
                <option key={logement.id} value={logement.id}>{logement.nom}</option>
              ))}
            </select>
          </label>
          <label>
            Libellé
            <input
              value={depense.libelle}
              onChange={(evenement) => setDepense({ ...depense, libelle: evenement.target.value })}
              required
            />
          </label>
          <label>
            Montant (FCFA)
            <input
              type="number"
              inputMode="numeric"
              min="1"
              step="1"
              value={depense.montant}
              onChange={(evenement) => setDepense({ ...depense, montant: evenement.target.value })}
              required
            />
          </label>
          <label>
            Date
            <input
              type="date"
              value={depense.date}
              onChange={(evenement) => setDepense({ ...depense, date: evenement.target.value })}
              required
            />
          </label>
          <button type="submit" className="bouton" disabled={enregistrement}>
            {enregistrement ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </form>
      ) : null}
      {!saisie ? (
        <>
          <h2 className="sous-titre">Séjours</h2>
          {!chargement && reservations.length === 0 ? (
            <Vide titre="Aucun encaissement à suivre" texte="Les séjours et leurs montants s’afficheront ici." />
          ) : null}
          {reservations.length > 0 ? (
            <ul className="cartes">
              {reservations.map((reservation) => (
                <li key={reservation.id} className={reservation.annulee ? 'carte carte-annulee' : 'carte'}>
                  <div className="carte-entete">
                    <h3>{reservation.client_nom}</h3>
                    <BadgeCanal canal={reservation.canal} libelle={reservation.canal_libelle} />
                  </div>
                  <p className="lieu">{reservation.logement_nom}</p>
                  {reservation.annulee ? <p><span className="badge badge-annulee">Annulée</span></p> : null}
                  <p className="ligne-montant">
                    <span>Prévu</span>
                    <strong>{formatFcfa(reservation.montant_total_prevu)}</strong>
                  </p>
                  <p className="ligne-montant">
                    <span>Encaissé</span>
                    <strong>{formatFcfa(reservation.montant_encaisse)}</strong>
                  </p>
                  {reservation.annulee ? (
                    <p className="aide">
                      {reservation.montant_encaisse > 0
                        ? 'Cet encaissement ne compte plus dans le reste à recevoir.'
                        : 'Ce séjour ne compte plus dans le prévu.'}
                    </p>
                  ) : (
                    <p className="ligne-montant">
                      <span>Reste</span>
                      <strong>{formatFcfa(reservation.reste_a_recevoir)}</strong>
                    </p>
                  )}
                </li>
              ))}
            </ul>
          ) : null}
          <h2 className="sous-titre">Dépenses</h2>
          {!chargement && depenses.length === 0 ? (
            <Vide titre="Aucune dépense" texte="Une course, une réparation, un abonnement : notez-le ici." />
          ) : null}
          {depenses.length > 0 ? (
            <ul className="cartes">
              {depenses.map((item) => (
                <li key={item.id} className="carte">
                  <h3>{item.libelle}</h3>
                  <p className="lieu">{item.logement_nom}</p>
                  <p className="ligne-montant">
                    <span>{formatDate(item.date)}</span>
                    <strong>{formatFcfa(item.montant)}</strong>
                  </p>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      ) : null}
    </section>
  )
}
