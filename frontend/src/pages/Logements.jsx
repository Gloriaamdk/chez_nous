import { useEffect, useState } from 'react'
import {
  createLogement,
  getLogements,
  getReferentiels,
  lienAbsolu,
  nouveauLienIcal,
  synchroniserAirbnb,
  updateLogement,
} from '../api.js'
import { formaterMoment, messageErreur } from '../format.js'
import { Alerte, Chargement, PastilleStatut, Vide } from '../interface.jsx'

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
  return `Airbnb : ${resultat.resume || 'synchronisé'} · ${formaterMoment(logement.synchro_le)}`
}

export default function Logements() {
  const [logements, setLogements] = useState([])
  const [types, setTypes] = useState([])
  const [pays, setPays] = useState([])
  const [filtrePays, setFiltrePays] = useState('')
  const [formulaire, setFormulaire] = useState(null)
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(true)
  const [enregistrement, setEnregistrement] = useState(false)
  const [synchroEnCours, setSynchroEnCours] = useState(false)
  const [info, setInfo] = useState('')

  async function charger() {
    const biens = await getLogements()
    setLogements(biens)
    return biens
  }

  useEffect(() => {
    let ignore = false
    getReferentiels()
      .then((data) => {
        if (!ignore) {
          setTypes(data.types)
          setPays(data.pays)
        }
      })
      .catch(() => {
        if (!ignore) {
          setErreur('La liste des pays est indisponible.')
        }
      })
    getLogements()
      .then((biens) => {
        if (!ignore) {
          setLogements(biens)
        }
      })
      .catch(() => {
        if (!ignore) {
          setErreur('Les logements sont indisponibles.')
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
    setErreur('')
    setInfo('')
    setFormulaire({ ...formulaireVide })
    window.scrollTo(0, 0)
  }

  function ouvrirModification(logement) {
    setErreur('')
    setInfo('')
    setFormulaire(champsLogement(logement))
    window.scrollTo(0, 0)
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
      window.scrollTo(0, 0)
    } catch (error) {
      setErreur(messageErreur(error))
    } finally {
      setEnregistrement(false)
    }
  }

  async function rechargerFormulaire(identifiant) {
    const biens = await getLogements()
    setLogements(biens)
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

  if (formulaire) {
    return (
      <section className="page">
        <button
          className="retour"
          type="button"
          onClick={() => {
            setFormulaire(null)
            window.scrollTo(0, 0)
          }}
        >
          ← Logements
        </button>
        <h1>{formulaire.id ? formulaire.nom || 'Fiche du logement' : 'Nouveau logement'}</h1>
        <p className="chapo">
          {formulaire.id
            ? 'Nom, adresse, et calendrier Airbnb.'
            : 'Le nom, le type, le pays et la ville suffisent pour commencer.'}
        </p>
        <form className="formulaire" onSubmit={enregistrer}>
          <h2>Le logement</h2>
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
              inputMode="url"
              value={formulaire.url_ical_airbnb || ''}
              onChange={modifierChamp}
              autoComplete="off"
              spellCheck={false}
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
              <div className="actions actions-colonne">
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
              {info ? <Alerte info>{info}</Alerte> : null}
              <p>
                {formulaire.synchro_le
                  ? `Dernière synchronisation : ${formaterMoment(formulaire.synchro_le)}`
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
          {erreur ? <Alerte>{erreur}</Alerte> : null}
          <div className="actions">
            <button type="submit" className="bouton" disabled={enregistrement}>
              {enregistrement ? 'Enregistrement…' : 'Enregistrer'}
            </button>
            <button
              type="button"
              className="bouton bouton-secondaire"
              onClick={() => {
                setFormulaire(null)
                window.scrollTo(0, 0)
              }}
            >
              Annuler
            </button>
          </div>
        </form>
      </section>
    )
  }

  return (
    <section className="page">
      <div className="page-entete">
        <div>
          <h1>Logements</h1>
          <p className="chapo">Le statut du jour, la ville, et la fiche Airbnb.</p>
        </div>
        <button type="button" className="bouton" onClick={ouvrirCreation}>
          Ajouter un logement
        </button>
      </div>
      {chargement ? <Chargement texte="Chargement des logements…" /> : null}
      {erreur ? <Alerte>{erreur}</Alerte> : null}
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
      {!chargement && logementsFiltres.length === 0 ? (
        <Vide
          titre={logements.length === 0 ? 'Aucun logement pour le moment' : 'Aucun logement dans ce pays'}
          texte={logements.length === 0
            ? 'Ajoutez le studio ou le chambre-salon. Vous pourrez en ajouter d’autres ensuite.'
            : 'Choisissez « Tous les pays » pour revoir la liste.'}
          action={logements.length === 0 ? (
            <button type="button" className="bouton" onClick={ouvrirCreation}>
              Ajouter un logement
            </button>
          ) : null}
        />
      ) : null}
      {logementsFiltres.length > 0 ? (
        <ul className="cartes">
          {logementsFiltres.map((logement) => {
            const airbnb = ligneAirbnb(logement)
            const airbnbEnErreur = Boolean(
              logement.synchro_resultat?.erreur || (logement.synchro_resultat?.conflits || []).length,
            )
            return (
              <li key={logement.id} className="carte">
                <h3>{logement.nom}</h3>
                <p className="lieu">{logement.type_libelle}</p>
                <p>
                  {logement.localisation_a_completer
                    ? 'Localisation à compléter'
                    : `${logement.ville}, ${logement.pays_libelle}`}
                </p>
                <PastilleStatut
                  etat={logement.statut_du_jour?.etat}
                  libelle={logement.statut_du_jour?.libelle || 'Statut indisponible'}
                />
                {airbnb ? (
                  <p className={airbnbEnErreur ? 'alerte alerte-inline' : 'aide'}>{airbnb}</p>
                ) : null}
                <button
                  type="button"
                  className="bouton bouton-secondaire"
                  onClick={() => ouvrirModification(logement)}
                >
                  Ouvrir la fiche
                </button>
              </li>
            )
          })}
        </ul>
      ) : null}
    </section>
  )
}
