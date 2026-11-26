import { useEffect, useState } from 'react'
import {
  annulerReservation,
  createReservation,
  formatFcfa,
  getLogements,
  getReferentiels,
  getReservations,
  updateReservation,
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
  blocage: false,
  code_airbnb: '',
  nombre_voyageurs: '',
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
  const [edition, setEdition] = useState(null)
  const [confirmation, setConfirmation] = useState(null)
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
    setEdition(null)
    setConfirmation(null)
    setFormulaire((actuel) => ({
      ...formulaireVide,
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

  function ouvrirCreation() {
    setEdition(null)
    setConfirmation(null)
    setFormulaire(formulaireVide)
    setErreur('')
    setOuvert(true)
  }

  function ouvrirModification(reservation) {
    setConfirmation(null)
    setErreur('')
    setEdition({
      id: reservation.id,
      montantEncaisse: reservation.montant_encaisse,
    })
    setFormulaire({
      logement: reservation.logement,
      client_nom: reservation.client_nom,
      client_telephone: reservation.client_telephone,
      canal: reservation.canal,
      mode: reservation.mode,
      date_arrivee: reservation.date_arrivee,
      date_depart: reservation.date_depart,
      montant_prevu: String(reservation.montant_prevu),
      acompte: '',
      blocage: Boolean(reservation.blocage),
      code_airbnb: reservation.code_airbnb || '',
      nombre_voyageurs: reservation.nombre_voyageurs ? String(reservation.nombre_voyageurs) : '',
    })
    setOuvert(true)
  }

  function fermerFormulaire() {
    setOuvert(false)
    setEdition(null)
    setFormulaire(formulaireVide)
  }

  async function enregistrer(evenement) {
    evenement.preventDefault()
    setEnregistrement(true)
    setErreur('')
    const payload = {
      logement: formulaire.logement,
      client_nom: formulaire.client_nom,
      client_telephone: formulaire.client_telephone,
      canal: formulaire.canal,
      mode: formulaire.mode,
      date_arrivee: formulaire.date_arrivee,
      date_depart: formulaire.date_depart,
    }
    if (!formulaire.blocage) {
      payload.montant_prevu = Number(formulaire.montant_prevu)
    }
    if (formulaire.canal === 'airbnb') {
      payload.code_airbnb = formulaire.code_airbnb.trim().toUpperCase()
      payload.nombre_voyageurs = formulaire.nombre_voyageurs
        ? Number(formulaire.nombre_voyageurs)
        : null
    }
    try {
      if (edition) {
        await updateReservation(edition.id, payload)
      } else {
        await createReservation({
          ...payload,
          acompte: formulaire.acompte ? Number(formulaire.acompte) : 0,
        })
      }
      await charger()
      fermerFormulaire()
    } catch (error) {
      setErreur(messageErreur(error))
    } finally {
      setEnregistrement(false)
    }
  }

  async function confirmerAnnulation(evenement) {
    evenement.preventDefault()
    setEnregistrement(true)
    setErreur('')
    try {
      await annulerReservation(confirmation.id)
      await charger()
      setConfirmation(null)
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
        {ouvert || confirmation ? null : (
          <button type="button" className="bouton" onClick={ouvrirCreation}>
            Nouvelle réservation
          </button>
        )}
      </div>
      {brouillon && ouvert && !edition ? (
        <p className="intro">Les dates et le logement choisis dans le calendrier sont conservés.</p>
      ) : null}
      {confirmation ? (
        <form className="formulaire" onSubmit={confirmerAnnulation}>
          <h2>Annuler la réservation</h2>
          <p>
            Le séjour de {confirmation.client_nom} reste dans l’historique.
            Les dates redeviennent libres et il ne comptera plus dans le prévu.
          </p>
          {confirmation.montant_encaisse > 0 ? (
            <p>
              {formatFcfa(confirmation.montant_encaisse)} déjà encaissés restent enregistrés.
              À rembourser si besoin.
            </p>
          ) : null}
          {erreur ? <p className="erreur">{erreur}</p> : null}
          <div className="actions">
            <button type="submit" className="bouton bouton-danger" disabled={enregistrement}>
              Confirmer l’annulation
            </button>
            <button
              type="button"
              className="bouton bouton-secondaire"
              onClick={() => setConfirmation(null)}
            >
              Retour
            </button>
          </div>
        </form>
      ) : null}
      {ouvert ? (
        <form className="formulaire" onSubmit={enregistrer}>
          <h2>{edition ? 'Modifier la réservation' : 'Nouvelle réservation'}</h2>
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
          {formulaire.blocage ? (
            <p className="intro">
              Blocage Airbnb : ces dates restent occupées, sans montant à recevoir.
              La prochaine synchronisation peut les réécrire.
            </p>
          ) : (
            <label>
              {formulaire.mode === 'mois' ? 'Loyer mensuel (FCFA)' : 'Montant du séjour (FCFA)'}
              <input name="montant_prevu" type="number" min="1" step="1" value={formulaire.montant_prevu} onChange={modifierChamp} required />
            </label>
          )}
          {formulaire.canal === 'airbnb' && !formulaire.blocage ? (
            <p className="intro">
              Séjour Airbnb. Le calendrier ne donne ni le nom ni le prix : les e-mails les complètent,
              sinon saisissez-les ici.
            </p>
          ) : null}
          {formulaire.canal === 'airbnb' ? (
            <>
              <label>
                Code de confirmation
                <input name="code_airbnb" value={formulaire.code_airbnb} onChange={modifierChamp} autoComplete="off" />
              </label>
              <label>
                Voyageurs
                <input name="nombre_voyageurs" type="number" min="1" step="1" value={formulaire.nombre_voyageurs} onChange={modifierChamp} />
              </label>
            </>
          ) : null}
          {edition ? (
            <p className="intro">
              {edition.montantEncaisse > 0
                ? `${formatFcfa(edition.montantEncaisse)} déjà encaissés restent attachés à ce séjour.`
                : 'Les encaissements déjà enregistrés restent attachés à ce séjour.'}
            </p>
          ) : (
            <label>
              Acompte encaissé (FCFA)
              <input name="acompte" type="number" min="0" step="1" value={formulaire.acompte} onChange={modifierChamp} />
            </label>
          )}
          {erreur ? <p className="erreur">{erreur}</p> : null}
          <div className="actions">
            <button type="submit" className="bouton" disabled={enregistrement}>Enregistrer</button>
            <button type="button" className="bouton bouton-secondaire" onClick={fermerFormulaire}>Fermer</button>
          </div>
        </form>
      ) : null}
      {!ouvert && erreur ? <p className="erreur">{erreur}</p> : null}
      {reservations.length === 0 ? (
        <p className="vide">Aucune réservation pour le moment.</p>
      ) : (
        <ul className="cartes">
          {reservations.map((reservation) => (
            <li key={reservation.id} className={reservation.annulee ? 'carte carte-annulee' : 'carte'}>
              <h3>{reservation.client_nom}</h3>
              <p>{reservation.logement_nom}</p>
              <p>{reservation.date_arrivee} → {reservation.date_depart}</p>
              <p>{reservation.mode_libelle} · {reservation.canal_libelle}</p>
              {reservation.blocage ? <p className="badge-blocage">Blocage Airbnb</p> : null}
              {!reservation.annulee && !reservation.blocage && reservation.canal === 'airbnb' && reservation.montant_prevu === 0 ? (
                <p className="badge-airbnb">À compléter</p>
              ) : null}
              {reservation.code_airbnb ? <p>Code Airbnb : {reservation.code_airbnb}</p> : null}
              {reservation.nombre_voyageurs ? (
                <p>{reservation.nombre_voyageurs} voyageur{reservation.nombre_voyageurs > 1 ? 's' : ''}</p>
              ) : null}
              {reservation.blocage ? (
                <p>Ces dates sont occupées. Ce blocage ne compte pas dans les sommes à recevoir.</p>
              ) : null}
              {reservation.annulee ? (
                <>
                  <p className="badge-annulee">Annulée{reservation.annulee_le ? ` le ${reservation.annulee_le}` : ''}</p>
                  {reservation.montant_encaisse > 0 ? (
                    <p>Encaissé conservé : {formatFcfa(reservation.montant_encaisse)}</p>
                  ) : null}
                  <p>Ce séjour ne compte plus dans le prévu. Les dates sont libres.</p>
                </>
              ) : (
                <>
                  <p>Prévu : {formatFcfa(reservation.montant_total_prevu)}</p>
                  <p>Encaissé : {formatFcfa(reservation.montant_encaisse)}</p>
                  <p>Reste : {formatFcfa(reservation.reste_a_recevoir)}</p>
                  <div className="actions-carte">
                    <button type="button" className="bouton bouton-secondaire" onClick={() => ouvrirModification(reservation)}>
                      Modifier
                    </button>
                    <button
                      type="button"
                      className="bouton bouton-danger"
                      onClick={() => {
                        setOuvert(false)
                        setEdition(null)
                        setErreur('')
                        setConfirmation(reservation)
                      }}
                    >
                      Annuler la réservation
                    </button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
