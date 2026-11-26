import { useEffect, useState } from 'react'
import { formatFcfa, getRapport } from '../api.js'
import { Alerte, Chargement, Vide } from '../interface.jsx'

function decaler(dateIso, periode, sens) {
  const date = new Date(`${dateIso}T12:00:00`)
  if (periode === 'semaine') {
    date.setDate(date.getDate() + sens * 7)
  } else {
    date.setMonth(date.getMonth() + sens)
  }
  return date.toISOString().slice(0, 10)
}

function ecartNombre(valeur, unite) {
  const signe = valeur > 0 ? '+' : ''
  return `${signe}${valeur} ${unite}`
}

function ecartFcfa(valeur) {
  const texte = formatFcfa(Math.abs(valeur))
  if (valeur > 0) {
    return `+${texte}`
  }
  if (valeur < 0) {
    return `−${texte}`
  }
  return texte
}

function Bloc({ titre, chiffres }) {
  return (
    <article className="carte">
      <h3>{titre}</h3>
      <p className="ligne-montant">
        <span>Occupation</span>
        <strong>{chiffres.taux_occupation} %</strong>
      </p>
      <p className="aide">{chiffres.nuits_occupees} nuits occupées</p>
      <p className="ligne-montant">
        <span>Encaissements</span>
        <strong>{formatFcfa(chiffres.encaissements)}</strong>
      </p>
      <p className="ligne-montant">
        <span>Dépenses</span>
        <strong>{formatFcfa(chiffres.depenses)}</strong>
      </p>
      <p className="aide">
        Période précédente : {chiffres.precedent.taux_occupation} %, {formatFcfa(chiffres.precedent.encaissements)} encaissés, {formatFcfa(chiffres.precedent.depenses)} de dépenses.
      </p>
      <p className="ecart">
        Écart : {ecartNombre(chiffres.ecart.taux_occupation, 'points')}, {ecartFcfa(chiffres.ecart.encaissements)} encaissés, {ecartFcfa(chiffres.ecart.depenses)} de dépenses.
      </p>
    </article>
  )
}

export default function Rapports({ onRetour }) {
  const [periode, setPeriode] = useState('mois')
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [rapport, setRapport] = useState(null)
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(true)

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
      .finally(() => {
        if (!cancelled) {
          setChargement(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [periode, date])

  return (
    <section className="page">
      {onRetour ? (
        <button className="retour" type="button" onClick={onRetour}>
          ← Plus
        </button>
      ) : null}
      <h1>Rapports</h1>
      <p className="chapo">Occupation, encaissements et dépenses, comparés à la période précédente.</p>
      <div className="segment">
        <button
          type="button"
          className={periode === 'semaine' ? 'bouton' : 'bouton bouton-secondaire'}
          aria-pressed={periode === 'semaine'}
          onClick={() => {
            setChargement(true)
            setPeriode('semaine')
          }}
        >
          Semaine
        </button>
        <button
          type="button"
          className={periode === 'mois' ? 'bouton' : 'bouton bouton-secondaire'}
          aria-pressed={periode === 'mois'}
          onClick={() => {
            setChargement(true)
            setPeriode('mois')
          }}
        >
          Mois
        </button>
      </div>
      <div className="actions actions-haut">
        <button
          type="button"
          className="bouton bouton-secondaire"
          onClick={() => {
            setChargement(true)
            setDate((actuelle) => decaler(actuelle, periode, -1))
          }}
        >
          Précédente
        </button>
        <button
          type="button"
          className="bouton bouton-secondaire"
          onClick={() => {
            setChargement(true)
            setDate((actuelle) => decaler(actuelle, periode, 1))
          }}
        >
          Suivante
        </button>
      </div>
      {chargement ? <Chargement texte="Préparation du bilan…" /> : null}
      {erreur ? <Alerte>{erreur}</Alerte> : null}
      {rapport ? (
        <>
          <h2 className="sous-titre">{rapport.libelle}</h2>
          <p className="chapo">{`Période précédente : ${rapport.precedente.libelle}.`}</p>
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
            <Vide titre="Ajoutez un logement pour obtenir un bilan" texte="Le total et le détail par logement apparaîtront ensuite." />
          ) : null}
        </>
      ) : null}
    </section>
  )
}
