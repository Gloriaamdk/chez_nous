import { useState } from 'react'
import { connecter } from '../api.js'

export default function Connexion({ sessionExpiree, onConnectee }) {
  const [identifiant, setIdentifiant] = useState('')
  const [motDePasse, setMotDePasse] = useState('')
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  async function soumettre(evenement) {
    evenement.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      const profil = await connecter(identifiant.trim(), motDePasse)
      onConnectee(profil)
    } catch (error) {
      setErreur(error.details?.detail || 'Connexion impossible. Réessayez.')
    } finally {
      setEnCours(false)
    }
  }

  return (
    <main className="page">
      <h1>Connexion</h1>
      <p className="intro">
        Réservé à la propriétaire et aux comptes créés dans l’administration.
      </p>
      {sessionExpiree ? (
        <p className="erreur session-expiree" role="status">
          Votre session a expiré. Reconnectez-vous.
        </p>
      ) : null}
      <form className="formulaire" onSubmit={soumettre}>
        <label>
          Identifiant
          <input
            name="identifiant"
            autoComplete="username"
            value={identifiant}
            onChange={(evenement) => {
              setIdentifiant(evenement.target.value)
              setErreur('')
            }}
            required
          />
        </label>
        <label>
          Mot de passe
          <input
            name="mot_de_passe"
            type="password"
            autoComplete="current-password"
            value={motDePasse}
            onChange={(evenement) => {
              setMotDePasse(evenement.target.value)
              setErreur('')
            }}
            required
          />
        </label>
        {erreur ? (
          <p className="erreur" role="alert">
            {erreur}
          </p>
        ) : null}
        <button className="bouton" type="submit" disabled={enCours}>
          {enCours ? 'Connexion…' : 'Se connecter'}
        </button>
      </form>
    </main>
  )
}
