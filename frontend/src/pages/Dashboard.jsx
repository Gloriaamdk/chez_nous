import { useEffect, useState } from 'react'
import {
  createLogement,
  formatFcfa,
  getLogements,
  getReferentiels,
  getTableauDeBord,
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

function classeStatut(etat) {
  if (etat === 'libre') {
    return 'libre'
  }
  if (etat === 'occupe') {
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
  const [tableau, setTableau] = useState(null)

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
      await charger()
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
              <p className={classeStatut(logement.statut_du_jour?.etat)}>
                {logement.statut_du_jour?.libelle || 'Statut indisponible'}
              </p>
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
