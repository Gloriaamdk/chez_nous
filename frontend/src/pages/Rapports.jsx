import { useEffect, useState } from 'react'
import { formatFcfa, getRapport } from '../api.js'

function decaler(dateIso, periode, sens) {
  const date = new Date(`${dateIso}T12:00:00`)
  if (periode === 'semaine') {
    date.setDate(date.getDate() + sens * 7)
  } else {
    date.setMonth(date.getMonth() + sens)
  }
  return date.toISOString().slice(0, 10)
}

function signe(valeur) {
  if (valeur > 0) {
    return `+${valeur}`
  }
  return String(valeur)
}

function Bloc({ titre, chiffres }) {
  return (
    <article className="carte">
      <h3>{titre}</h3>
      <p>Occupation : {chiffres.taux_occupation} % ({chiffres.nuits_occupees} nuits)</p>
      <p>Encaissements : {formatFcfa(chiffres.encaissements)}</p>
      <p>Dépenses : {formatFcfa(chiffres.depenses)}</p>
      <p className="intro">
        Période précédente : {chiffres.precedent.taux_occupation} %, {formatFcfa(chiffres.precedent.encaissements)} encaissés, {formatFcfa(chiffres.precedent.depenses)} de dépenses.
      </p>
      <p>
        Écart : {signe(chiffres.ecart.taux_occupation)} points, {signe(chiffres.ecart.encaissements)} FCFA encaissés, {signe(chiffres.ecart.depenses)} FCFA de dépenses.
      </p>
    </article>
  )
}

export default function Rapports() {
  const [periode, setPeriode] = useState('mois')
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [rapport, setRapport] = useState(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    let cancelled = false
    getRapport(periode, date)
      .then((data) => {
        if (!cancelled) {
          setRapport(data)
          setErreur('')
        }
      })
      .catch(() => {
        if (!cancelled) {
          setErreur('Le rapport est indisponible.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [periode, date])

  return (
    <section className="page">
      <h1>Rapports</h1>
      <div className="actions actions-haut">
        <button
          type="button"
          className={periode === 'semaine' ? 'bouton' : 'bouton bouton-secondaire'}
          onClick={() => setPeriode('semaine')}
        >
          Semaine
        </button>
        <button
          type="button"
          className={periode === 'mois' ? 'bouton' : 'bouton bouton-secondaire'}
          onClick={() => setPeriode('mois')}
        >
          Mois
        </button>
      </div>
      <div className="actions actions-haut">
        <button type="button" className="bouton bouton-secondaire" onClick={() => setDate((actuelle) => decaler(actuelle, periode, -1))}>
          Précédente
        </button>
        <button type="button" className="bouton bouton-secondaire" onClick={() => setDate((actuelle) => decaler(actuelle, periode, 1))}>
          Suivante
        </button>
      </div>
      {erreur ? <p className="erreur">{erreur}</p> : null}
      {rapport ? (
        <>
          <h2 className="sous-titre">{rapport.libelle}</h2>
          <p className="intro">{`Période précédente : ${rapport.precedente.libelle}.`}</p>
          <ul className="cartes">
            <li>
              <Bloc titre="Total" chiffres={rapport.total} />
            </li>
            {rapport.logements.map((logement) => (
              <li key={logement.id}>
                <Bloc titre={logement.nom} chiffres={logement} />
              </li>
            ))}
          </ul>
          {rapport.logements.length === 0 ? (
            <p className="vide">Ajoutez un logement pour obtenir un bilan.</p>
          ) : null}
        </>
      ) : null}
    </section>
  )
}
