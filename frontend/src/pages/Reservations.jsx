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
import { formatDate, formatPlage, messageErreur } from '../format.js'
import { Alerte, BadgeCanal, Chargement, Vide } from '../interface.jsx'

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

function formulaireDepuisCalendrier(brouillon) {
  return {
    ...formulaireVide,
    logement: brouillon.logementId,
    date_arrivee: brouillon.arrivee,
    date_depart: brouillon.depart,
  }
}

export default function Reservations({ brouillon, intention }) {
  const depuisCalendrier = Boolean(brouillon)
  const [logements, setLogements] = useState([])
  const [canaux, setCanaux] = useState([])
  const [modes, setModes] = useState([])
  const [reservations, setReservations] = useState([])
  const [formulaire, setFormulaire] = useState(() => (
    depuisCalendrier ? formulaireDepuisCalendrier(brouillon) : formulaireVide
  ))
  const [ouvert, setOuvert] = useState(depuisCalendrier || intention?.action === 'creer')
  const [edition, setEdition] = useState(null)
  const [confirmation, setConfirmation] = useState(null)
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(true)
  const [enregistrement, setEnregistrement] = useState(false)

  async function charger() {
    setReservations(await getReservations())
  }

  useEffect(() => {
    let ignore = false
    Promise.all([getLogements(), getReferentiels(), getReservations()])
      .then(([biens, refs, sejours]) => {
        if (ignore) {
          return
        }
        setLogements(biens)
        setCanaux(refs.canaux)
        setModes(refs.modes)
        setReservations(sejours)
      })
      .catch(() => {
        if (!ignore) {
          setErreur('Les réservations sont indisponibles.')
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
    window.scrollTo(0, 0)
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
    window.scrollTo(0, 0)
  }

  function fermerFormulaire() {
    setOuvert(false)
    setEdition(null)
    setFormulaire(formulaireVide)
    window.scrollTo(0, 0)
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

  const formulaireOuvert = ouvert || confirmation

  return (
    <section className="page">
      {!formulaireOuvert ? (
        <div className="page-entete">
          <div>
            <h1>Réservations</h1>
            <p className="chapo">Nuitée ou mois, acompte, et annulation sans perdre l’historique.</p>
          </div>
          <button type="button" className="bouton" onClick={ouvrirCreation}>
            Nouvelle réservation
          </button>
        </div>
      ) : (
        <button
          className="retour"
          type="button"
          onClick={() => {
            setConfirmation(null)
            fermerFormulaire()
          }}
        >
          ← Réservations
        </button>
      )}

      {brouillon && ouvert && !edition ? (
        <p className="note">Les dates et le logement choisis dans le calendrier sont conservés.</p>
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
          {erreur ? <Alerte>{erreur}</Alerte> : null}
          <div className="actions">
            <button type="submit" className="bouton bouton-danger" disabled={enregistrement}>
              {enregistrement ? 'Annulation…' : 'Confirmer l’annulation'}
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
            <input
              name="client_nom"
              value={formulaire.client_nom}
              onChange={modifierChamp}
              autoComplete="name"
              required
            />
          </label>
          <label>
            Téléphone
            <input
              name="client_telephone"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              value={formulaire.client_telephone}
              onChange={modifierChamp}
              required
            />
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
            <p className="aide">
              Blocage Airbnb : ces dates restent occupées, sans montant à recevoir.
              La prochaine synchronisation peut les réécrire.
            </p>
          ) : (
            <label>
              {formulaire.mode === 'mois' ? 'Loyer mensuel (FCFA)' : 'Montant du séjour (FCFA)'}
              <input
                name="montant_prevu"
                type="number"
                inputMode="numeric"
                min="1"
                step="1"
                value={formulaire.montant_prevu}
                onChange={modifierChamp}
                required
              />
            </label>
          )}
          {formulaire.canal === 'airbnb' && !formulaire.blocage ? (
            <p className="aide">
              Séjour Airbnb. Le calendrier ne donne ni le nom ni le prix : les e-mails les complètent,
              sinon saisissez-les ici.
            </p>
          ) : null}
          {formulaire.canal === 'airbnb' ? (
            <>
              <label>
                Code de confirmation
                <input
                  name="code_airbnb"
                  value={formulaire.code_airbnb}
                  onChange={modifierChamp}
                  autoComplete="off"
                  autoCapitalize="characters"
                  autoCorrect="off"
                  spellCheck={false}
                />
              </label>
              <label>
                Voyageurs
                <input
                  name="nombre_voyageurs"
                  type="number"
                  inputMode="numeric"
                  min="1"
                  step="1"
                  value={formulaire.nombre_voyageurs}
                  onChange={modifierChamp}
                />
              </label>
            </>
          ) : null}
          {edition ? (
            <p className="aide">
              {edition.montantEncaisse > 0
                ? `${formatFcfa(edition.montantEncaisse)} déjà encaissés restent attachés à ce séjour.`
                : 'Les encaissements déjà enregistrés restent attachés à ce séjour.'}
            </p>
          ) : (
            <label>
              Acompte encaissé (FCFA)
              <input
                name="acompte"
                type="number"
                inputMode="numeric"
                min="0"
                step="1"
                value={formulaire.acompte}
                onChange={modifierChamp}
              />
            </label>
          )}
          {erreur ? <Alerte>{erreur}</Alerte> : null}
          <div className="actions">
            <button type="submit" className="bouton" disabled={enregistrement}>
              {enregistrement ? 'Enregistrement…' : 'Enregistrer'}
            </button>
            <button type="button" className="bouton bouton-secondaire" onClick={fermerFormulaire}>
              Fermer
            </button>
          </div>
        </form>
      ) : null}

      {!formulaireOuvert && chargement ? <Chargement texte="Chargement des réservations…" /> : null}
      {!formulaireOuvert && erreur ? <Alerte>{erreur}</Alerte> : null}
      {!formulaireOuvert && !chargement && reservations.length === 0 ? (
        <Vide
          titre="Aucune réservation pour le moment"
          texte="Pendant un appel, notez le séjour et l’acompte ici."
          action={(
            <button type="button" className="bouton" onClick={ouvrirCreation}>
              Nouvelle réservation
            </button>
          )}
        />
      ) : null}
      {!formulaireOuvert && reservations.length > 0 ? (
        <ul className="cartes">
          {reservations.map((reservation) => (
            <li key={reservation.id} className={reservation.annulee ? 'carte carte-annulee' : 'carte'}>
              <div className="carte-entete">
                <h3>{reservation.client_nom}</h3>
                <BadgeCanal canal={reservation.canal} libelle={reservation.canal_libelle} />
              </div>
              <p className="lieu">{reservation.logement_nom}</p>
              <p className="dates">{formatPlage(reservation.date_arrivee, reservation.date_depart)}</p>
              <p className="meta">{reservation.mode_libelle}</p>
              {reservation.blocage ? <p><span className="badge badge-blocage">Blocage Airbnb</span></p> : null}
              {!reservation.annulee && !reservation.blocage && reservation.canal === 'airbnb' && reservation.montant_prevu === 0 ? (
                <p><span className="badge badge-a-completer">À compléter</span></p>
              ) : null}
              {reservation.code_airbnb ? <p>Code Airbnb : {reservation.code_airbnb}</p> : null}
              {reservation.nombre_voyageurs ? (
                <p>{reservation.nombre_voyageurs} voyageur{reservation.nombre_voyageurs > 1 ? 's' : ''}</p>
              ) : null}
              {reservation.blocage ? (
                <p className="aide">Ces dates sont occupées. Ce blocage ne compte pas dans les sommes à recevoir.</p>
              ) : null}
              {reservation.annulee ? (
                <>
                  <p>
                    <span className="badge badge-annulee">
                      Annulée{reservation.annulee_le ? ` le ${formatDate(reservation.annulee_le)}` : ''}
                    </span>
                  </p>
                  {reservation.montant_encaisse > 0 ? (
                    <p className="ligne-montant">
                      <span>Encaissé conservé</span>
                      <strong>{formatFcfa(reservation.montant_encaisse)}</strong>
                    </p>
                  ) : null}
                  <p className="aide">Ce séjour ne compte plus dans le prévu. Les dates sont libres.</p>
                </>
              ) : (
                <>
                  <p className="ligne-montant">
                    <span>Prévu</span>
                    <strong>{formatFcfa(reservation.montant_total_prevu)}</strong>
                  </p>
                  <p className="ligne-montant">
                    <span>Encaissé</span>
                    <strong>{formatFcfa(reservation.montant_encaisse)}</strong>
                  </p>
                  <p className="ligne-montant">
                    <span>Reste</span>
                    <strong>{formatFcfa(reservation.reste_a_recevoir)}</strong>
                  </p>
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
                        window.scrollTo(0, 0)
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
      ) : null}
    </section>
  )
}
