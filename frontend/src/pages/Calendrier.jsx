import { useEffect, useState } from 'react'
import { getDisponibilites, getLogements } from '../api.js'

export default function Calendrier({ onChoisirLogement }) {
  const [arrivee, setArrivee] = useState('')
  const [depart, setDepart] = useState('')
  const [resultat, setResultat] = useState(null)
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(false)
  const [aucunLogement, setAucunLogement] = useState(false)

  useEffect(() => {
    getLogements()
      .then((logements) => setAucunLogement(logements.length === 0))
      .catch(() => setAucunLogement(false))
  }, [])

  async function verifier(evenement) {
    evenement.preventDefault()
    if (!arrivee || !depart || depart <= arrivee) {
      setErreur('Le départ doit être après l’arrivée.')
      setResultat(null)
      return
    }
    setChargement(true)
    setErreur('')
    try {
      setResultat(await getDisponibilites(arrivee, depart))
    } catch (error) {
      setResultat(null)
      setErreur(error.details?.detail || 'Impossible de vérifier les disponibilités.')
    } finally {
      setChargement(false)
    }
  }

  return (
    <section className="page">
      <h1>Calendrier</h1>
      <p className="intro">Choisissez deux dates pour voir quel logement est libre.</p>
      {aucunLogement ? (
        <p className="vide">Ajoutez d’abord un logement depuis le tableau de bord.</p>
      ) : null}
      <form className="formulaire" onSubmit={verifier}>
        <label>
          Arrivée
          <input type="date" value={arrivee} onChange={(evenement) => setArrivee(evenement.target.value)} required />
        </label>
        <label>
          Départ
          <input type="date" value={depart} onChange={(evenement) => setDepart(evenement.target.value)} required />
        </label>
        {erreur ? <p className="erreur">{erreur}</p> : null}
        <button type="submit" className="bouton" disabled={chargement}>
          Voir les logements libres
        </button>
      </form>
      {resultat ? (
        <ul className="cartes">
          {resultat.logements.map((logement) => (
            <li key={logement.id} className="carte">
              <h3>{logement.nom}</h3>
              <p>{logement.type_libelle}</p>
              <p className={logement.libre ? 'libre' : 'occupe'}>
                {logement.libre ? 'Libre' : 'Déjà réservé'}
              </p>
              {logement.libre ? (
                <button
                  type="button"
                  className="bouton"
                  onClick={() => onChoisirLogement({
                    logementId: logement.id,
                    arrivee,
                    depart,
                  })}
                >
                  Réserver ce logement
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
