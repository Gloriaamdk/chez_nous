import { useEffect, useState } from 'react'
import {
  createLogement,
  formatFcfa,
  getLectureEmails,
  getLogements,
  getReferentiels,
  getTableauDeBord,
  lienAbsolu,
  nouveauLienIcal,
  synchroniserAirbnb,
  updateLogement,
} from '../api.js'

const formulaireVide = {
  nom: '',
  type: 'studio',
  pays: '',
  ville: '',
  url_ical_airbnb: '',
  annonce_airbnb: '',
  chemin_ical: '',
  synchro_le: null,
  synchro_resultat: {},
}

function formaterSynchro(iso) {
  if (!iso) {
    return ''
  }
  return new Date(iso).toLocaleString('fr-FR', {
    timeZone: 'Africa/Lome',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function champsLogement(logement) {
  return {
    id: logement.id,
    nom: logement.nom,
    type: logement.type,
    pays: logement.pays,
    ville: logement.ville,
    url_ical_airbnb: logement.url_ical_airbnb || '',
    annonce_airbnb: logement.annonce_airbnb || '',
    chemin_ical: logement.chemin_ical || '',
    synchro_le: logement.synchro_le,
    synchro_resultat: logement.synchro_resultat || {},
  }
}

function ligneAirbnb(logement) {
  if (!logement.url_ical_airbnb && !logement.synchro_le) {
    return ''
  }
  const resultat = logement.synchro_resultat || {}
  if (!logement.synchro_le) {
    return 'Airbnb : adresse enregistrée, pas encore synchronisée.'
  }
  if (resultat.erreur) {
    return `Airbnb : ${resultat.erreur}`
  }
  return `Airbnb : ${resultat.resume || 'synchronisé'} · ${formaterSynchro(logement.synchro_le)}`
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

function classeStatut(etat) {
  if (etat === 'libre') {
    return 'libre'
  }
  if (etat === 'occupe' || etat === 'blocage') {
    return 'occupe'
  }
  return 'mouvement'
}

function LigneSejour({ sejour }) {
  return (
    <li className="carte">
      <h3>{sejour.client_nom}</h3>
      <p>{sejour.logement_nom}</p>
      <p>{sejour.date_arrivee} → {sejour.date_depart}</p>
    </li>
  )
}

export default function Dashboard() {
  const [logements, setLogements] = useState([])
  const [types, setTypes] = useState([])
  const [pays, setPays] = useState([])
  const [filtrePays, setFiltrePays] = useState('')
  const [formulaire, setFormulaire] = useState(null)
  const [erreur, setErreur] = useState('')
  const [enregistrement, setEnregistrement] = useState(false)
  const [synchroEnCours, setSynchroEnCours] = useState(false)
  const [info, setInfo] = useState('')
  const [tableau, setTableau] = useState(null)
  const [lecture, setLecture] = useState(null)

  async function charger() {
    const [biens, resume] = await Promise.all([getLogements(), getTableauDeBord()])
    setLogements(biens)
    setTableau(resume)
  }

  useEffect(() => {
    let cancelled = false

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

    charger().catch(() => {
      if (!cancelled) {
        setErreur('Le tableau de bord est indisponible.')
      }
    })
    getLectureEmails()
      .then((data) => {
        if (!cancelled) {
          setLecture(data)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLecture(null)
        }
      })

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
    setInfo('')
    setFormulaire({ ...formulaireVide })
  }

  function ouvrirModification(logement) {
    setErreur('')
    setInfo('')
    setFormulaire(champsLogement(logement))
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
      url_ical_airbnb: (formulaire.url_ical_airbnb || '').trim(),
      annonce_airbnb: (formulaire.annonce_airbnb || '').trim(),
    }
    try {
      if (formulaire.id) {
        await updateLogement(formulaire.id, payload)
      } else {
        await createLogement(payload)
      }
      await charger()
      setFormulaire(null)
      setInfo('')
    } catch (error) {
      setErreur(messageErreur(error))
    } finally {
      setEnregistrement(false)
    }
  }

  async function rechargerFormulaire(identifiant) {
    const [biens, resume, emails] = await Promise.all([
      getLogements(),
      getTableauDeBord(),
      getLectureEmails(),
    ])
    setLogements(biens)
    setTableau(resume)
    setLecture(emails)
    const maj = biens.find((item) => item.id === identifiant)
    if (maj) {
      setFormulaire(champsLogement(maj))
    }
  }

  async function synchroniser() {
    const enregistre = logements.find((item) => item.id === formulaire.id)
    if ((enregistre?.url_ical_airbnb || '') !== (formulaire.url_ical_airbnb || '').trim()) {
      setErreur('Enregistrez d’abord l’adresse Airbnb.')
      setInfo('')
      return
    }
    setSynchroEnCours(true)
    setErreur('')
    setInfo('')
    try {
      const maj = await synchroniserAirbnb(formulaire.id)
      await rechargerFormulaire(formulaire.id)
      if (maj.synchro_resultat?.erreur) {
        setErreur(maj.synchro_resultat.erreur)
      } else {
        setInfo(maj.synchro_resultat?.resume || 'Synchronisation terminée.')
      }
    } catch (error) {
      setErreur(messageErreur(error))
    } finally {
      setSynchroEnCours(false)
    }
  }

  async function copierLien() {
    const url = lienAbsolu(formulaire.chemin_ical)
    try {
      await navigator.clipboard.writeText(url)
      setInfo('Lien copié.')
      setErreur('')
    } catch {
      setInfo('Sélectionnez le lien ci-dessus, puis copiez-le.')
    }
  }

  async function regenererLien() {
    if (!window.confirm('L’ancien lien ne fonctionnera plus dans Airbnb. Il faudra y coller le nouveau. Continuer ?')) {
      return
    }
    setErreur('')
    setInfo('')
    try {
      await nouveauLienIcal(formulaire.id)
      await rechargerFormulaire(formulaire.id)
      setInfo('Nouveau lien créé. Collez-le à nouveau dans Airbnb.')
    } catch (error) {
      setErreur(messageErreur(error))
    }
  }

  const paysPresents = pays.filter((item) =>
    logements.some((logement) => logement.pays === item.code),
  )
  const logementsFiltres = filtrePays
    ? logements.filter((logement) => logement.pays === filtrePays)
    : logements

  return (
    <section className="page">
      <h1>Tableau de bord</h1>
      {tableau ? (
        <div className="resume" role="status">
          <h2>{tableau.libelle_date}</h2>
          <p>{tableau.phrase}</p>
          <p>
            Arrivées du jour : {tableau.arrivees_aujourdhui.length === 0
              ? 'aucune'
              : tableau.arrivees_aujourdhui.map((sejour) => `${sejour.client_nom} (${sejour.logement_nom})`).join(', ')}
          </p>
          <p>
            Départs du jour : {tableau.departs_aujourdhui.length === 0
              ? 'aucun'
              : tableau.departs_aujourdhui.map((sejour) => `${sejour.client_nom} (${sejour.logement_nom})`).join(', ')}
          </p>
        </div>
      ) : null}

      {lecture ? (
        <div className="resume lecture">
          <h2>E-mails Airbnb</h2>
          {lecture.le ? (
            <p>Dernière lecture : {formaterSynchro(lecture.le)}</p>
          ) : (
            <p>Pas encore de lecture.</p>
          )}
          {lecture.resultat?.resume ? <p>{lecture.resultat.resume}</p> : null}
          {!lecture.configuree && !lecture.resultat?.resume ? (
            <p className="aide">
              Pour remplir les noms et les montants tout seuls, reliez la boîte mail
              (mot de passe d’application). La marche à suivre est dans le README.
            </p>
          ) : null}
          {(lecture.resultat?.notes || []).map((note) => (
            <p key={note}>{note}</p>
          ))}
        </div>
      ) : null}

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
          <h2>Calendrier Airbnb</h2>
          <p className="aide">
            Dans Airbnb : Calendrier, Disponibilité, Exporter le calendrier.
            Collez le lien ici. Les séjours arrivent avec le nom « Client Airbnb » ;
            les e-mails les complètent ensuite.
          </p>
          <label>
            Lien d’export Airbnb
            <input
              name="url_ical_airbnb"
              type="url"
              value={formulaire.url_ical_airbnb || ''}
              onChange={modifierChamp}
              autoComplete="off"
              placeholder="https://www.airbnb.com/calendar/ical/….ics"
            />
          </label>
          <label>
            Nom de l’annonce Airbnb
            <input
              name="annonce_airbnb"
              value={formulaire.annonce_airbnb || ''}
              onChange={modifierChamp}
              autoComplete="off"
              placeholder="Comme dans l’e-mail de confirmation"
            />
          </label>
          <p className="aide">
            Ce nom sert à rattacher les e-mails au bon logement. Recopiez-le tel qu’il est écrit dans le message.
          </p>
          {formulaire.id ? (
            <>
              <label>
                Lien à coller dans Airbnb
                <input className="lien-lecture" readOnly value={lienAbsolu(formulaire.chemin_ical)} />
              </label>
              <p className="aide">
                Dans Airbnb : Calendrier, Disponibilité, Importer un calendrier.
                Ce lien bloque les nuits déjà prises par WhatsApp ou par téléphone.
                Aucun nom de client n’est envoyé : seulement « Réservé ».
              </p>
              <div className="actions-airbnb">
                <button type="button" className="bouton bouton-secondaire" onClick={copierLien}>
                  Copier le lien
                </button>
                <button type="button" className="bouton bouton-secondaire" onClick={regenererLien}>
                  Nouveau lien
                </button>
                <button
                  type="button"
                  className="bouton"
                  onClick={synchroniser}
                  disabled={synchroEnCours || !(formulaire.url_ical_airbnb || '').trim()}
                >
                  {synchroEnCours ? 'Synchronisation…' : 'Synchroniser maintenant'}
                </button>
              </div>
              {info ? <p className="intro">{info}</p> : null}
              <p>
                {formulaire.synchro_le
                  ? `Dernière synchronisation : ${formaterSynchro(formulaire.synchro_le)}`
                  : 'Pas encore synchronisé.'}
              </p>
              {formulaire.synchro_resultat?.resume && !formulaire.synchro_resultat?.erreur ? (
                <p>{formulaire.synchro_resultat.resume}</p>
              ) : null}
              {(formulaire.synchro_resultat?.conflits || []).length > 0 ? (
                <ul className="conflits">
                  {formulaire.synchro_resultat.conflits.map((conflit) => (
                    <li key={`${conflit.uid}-${conflit.arrivee}-${conflit.message}`}>
                      {conflit.resume || 'Événement Airbnb'}
                      {conflit.arrivee ? `, du ${conflit.arrivee} au ${conflit.depart}` : ''}
                      {' : '}
                      {conflit.message}
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : (
            <p className="aide">Enregistrez le logement pour obtenir le lien à coller dans Airbnb.</p>
          )}
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
              <p className={classeStatut(logement.statut_du_jour?.etat)}>
                {logement.statut_du_jour?.libelle || 'Statut indisponible'}
              </p>
              {ligneAirbnb(logement) ? (
                <p className={logement.synchro_resultat?.erreur || (logement.synchro_resultat?.conflits || []).length ? 'erreur' : 'aide'}>
                  {ligneAirbnb(logement)}
                </p>
              ) : null}
              <button type="button" className="bouton bouton-secondaire" onClick={() => ouvrirModification(logement)}>
                Modifier
              </button>
            </li>
          ))}
        </ul>
      )}

      {tableau ? (
        <div className="montants">
          <p className="montant"><span>À recevoir</span>{formatFcfa(tableau.reste_a_recevoir)}</p>
          <p className="montant"><span>Encaissé</span>{formatFcfa(tableau.montant_encaisse)}</p>
          <p className="montant"><span>Dépenses</span>{formatFcfa(tableau.depenses)}</p>
          {tableau.montant_encaisse_annule > 0 ? (
            <p className="montant">
              <span>Encaissé sur un séjour annulé</span>
              {formatFcfa(tableau.montant_encaisse_annule)}
            </p>
          ) : null}
        </div>
      ) : null}

      <h2 className="sous-titre">Prochaines arrivées</h2>
      {tableau && tableau.prochaines_arrivees.length === 0 ? (
        <p className="vide">Aucune arrivée à venir.</p>
      ) : null}
      {tableau && tableau.prochaines_arrivees.length > 0 ? (
        <ul className="cartes">
          {tableau.prochaines_arrivees.map((sejour) => (
            <LigneSejour key={sejour.id} sejour={sejour} />
          ))}
        </ul>
      ) : null}

      <h2 className="sous-titre">Prochains départs</h2>
      {tableau && tableau.prochains_departs.length === 0 ? (
        <p className="vide">Aucun départ à venir.</p>
      ) : null}
      {tableau && tableau.prochains_departs.length > 0 ? (
        <ul className="cartes">
          {tableau.prochains_departs.map((sejour) => (
            <LigneSejour key={`depart-${sejour.id}`} sejour={sejour} />
          ))}
        </ul>
      ) : null}
    </section>
  )
}
