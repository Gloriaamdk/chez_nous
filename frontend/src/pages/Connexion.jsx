import { useState } from 'react'
import { connecter } from '../api.js'
import { Alerte } from '../interface.jsx'

export default function Connexion({ sessionExpiree, onConnectee }) {
  const [identifiant, setIdentifiant] = useState('')
  const [motDePasse, setMotDePasse] = useState('')
  const [afficher, setAfficher] = useState(false)
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
    <main className="carte-connexion">
      <h1 className="titre-connexion">Connexion</h1>
      <p className="chapo">
        Réservé à la propriétaire et aux comptes créés dans l’administration.
      </p>
      {sessionExpiree ? (
        <Alerte>Votre session a expiré. Reconnectez-vous.</Alerte>
      ) : null}
      <form className="formulaire" onSubmit={soumettre}>
        <label>
          Identifiant
          <input
            name="identifiant"
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
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
          <span className="champ-mot">
            <input
              name="mot_de_passe"
              type={afficher ? 'text' : 'password'}
              autoComplete="current-password"
              value={motDePasse}
              onChange={(evenement) => {
                setMotDePasse(evenement.target.value)
                setErreur('')
              }}
              required
            />
            <button
              className="bouton bouton-secondaire"
              type="button"
              onClick={() => setAfficher((valeur) => !valeur)}
            >
              {afficher ? 'Masquer' : 'Afficher'}
            </button>
          </span>
        </label>
        {erreur ? <Alerte>{erreur}</Alerte> : null}
        <button className="bouton bouton-large" type="submit" disabled={enCours}>
          {enCours ? 'Connexion…' : 'Se connecter'}
        </button>
      </form>
    </main>
  )
}
