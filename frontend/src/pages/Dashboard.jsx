import { useEffect, useState } from 'react'
import {
  formatFcfa,
  getLectureEmails,
  getLogements,
  getTableauDeBord,
  synchroniserAirbnb,
} from '../api.js'
import { capitale, formatPlage, formaterMoment, messageErreur } from '../format.js'
import {
  Alerte,
  Chargement,
  IconeAjout,
  IconeArgent,
  IconeSync,
  Vide,
} from '../interface.jsx'

function LigneSejour({ sejour, etiquette }) {
  return (
    <li className="carte">
      <div className="carte-entete">
        <h3>{sejour.client_nom}</h3>
        {etiquette ? <span className="badge badge-mouvement">{etiquette}</span> : null}
      </div>
      <p className="lieu">{sejour.logement_nom}</p>
      <p className="dates">{formatPlage(sejour.date_arrivee, sejour.date_depart)}</p>
    </li>
  )
}

export default function Dashboard({ profil, onAller }) {
  const [logements, setLogements] = useState([])
  const [tableau, setTableau] = useState(null)
  const [lecture, setLecture] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState('')
  const [synchro, setSynchro] = useState({ enCours: false, message: '', erreur: '' })

  async function charger() {
    const [biens, resume, emails] = await Promise.all([
      getLogements(),
      getTableauDeBord(),
      getLectureEmails().catch(() => null),
    ])
    setLogements(biens)
    setTableau(resume)
    setLecture(emails)
  }

  useEffect(() => {
    let ignore = false
    Promise.all([
      getLogements(),
      getTableauDeBord(),
      getLectureEmails().catch(() => null),
    ])
      .then(([biens, resume, emails]) => {
        if (ignore) {
          return
        }
        setLogements(biens)
        setTableau(resume)
        setLecture(emails)
      })
      .catch(() => {
        if (!ignore) {
          setErreur('Le tableau de bord est indisponible.')
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

  async function synchroniserTout() {
    setSynchro({ enCours: true, message: '', erreur: '' })
    try {
      const biens = logements.length ? logements : await getLogements()
      const cibles = biens.filter((logement) => (logement.url_ical_airbnb || '').trim())
      if (cibles.length === 0) {
        setSynchro({
          enCours: false,
          message: '',
          erreur: 'Aucun logement n’a encore de lien Airbnb. Ouvrez sa fiche pour le coller.',
        })
        return
      }
      const resultats = []
      for (const logement of cibles) {
        resultats.push(await synchroniserAirbnb(logement.id))
      }
      await charger()
      const enEchec = resultats.filter((item) => item.synchro_resultat?.erreur)
      if (enEchec.length > 0) {
        setSynchro({
          enCours: false,
          message: '',
          erreur: enEchec
            .map((item) => `${item.nom} : ${item.synchro_resultat.erreur}`)
            .join(' '),
        })
        return
      }
      setSynchro({
        enCours: false,
        message: resultats
          .map((item) => `${item.nom} : ${item.synchro_resultat?.resume || 'synchronisé'}`)
          .join(' · '),
        erreur: '',
      })
    } catch (error) {
      setSynchro({
        enCours: false,
        message: '',
        erreur: messageErreur(error, 'La synchronisation a échoué. Réessayez.'),
      })
    }
  }

  const prenom = (profil?.prenom || '').trim()
  const salutation = prenom ? `Bonjour ${prenom}` : 'Bonjour'

  return (
    <section className="page">
      <p className="jour">{tableau ? capitale(tableau.libelle_date) : 'Aujourd’hui'}</p>
      <h1>{salutation} <span aria-hidden="true">👋</span></h1>
      {chargement ? <Chargement texte="Préparation de la journée…" /> : null}
      {erreur ? (
        <>
          <Alerte>{erreur}</Alerte>
          <button
            className="bouton bouton-secondaire"
            type="button"
            onClick={() => {
              setChargement(true)
              setErreur('')
              charger()
                .catch(() => setErreur('Le tableau de bord est indisponible.'))
                .finally(() => setChargement(false))
            }}
          >
            Réessayer
          </button>
        </>
      ) : null}

      {tableau ? (
        <>
          <p className="phrase">{tableau.phrase}</p>
          <ul className="stats">
            <li>
              <span className="stats-valeur">{tableau.arrivees_aujourdhui.length}</span>
              <span className="stats-label">Arrivées</span>
              <span className="stats-detail">
                {tableau.arrivees_aujourdhui.length === 0
                  ? 'Aucune aujourd’hui'
                  : tableau.arrivees_aujourdhui.map((sejour) => sejour.client_nom).join(', ')}
              </span>
            </li>
            <li>
              <span className="stats-valeur">{tableau.departs_aujourdhui.length}</span>
              <span className="stats-label">Départs</span>
              <span className="stats-detail">
                {tableau.departs_aujourdhui.length === 0
                  ? 'Aucun aujourd’hui'
                  : tableau.departs_aujourdhui.map((sejour) => sejour.client_nom).join(', ')}
              </span>
            </li>
            <li>
              <span className="stats-valeur">{tableau.logements_occupes}</span>
              <span className="stats-label">Occupés</span>
              <span className="stats-detail">
                {tableau.logements_libres} libre{tableau.logements_libres > 1 ? 's' : ''}
              </span>
            </li>
            <li>
              <span className="stats-valeur stats-montant">{formatFcfa(tableau.reste_a_recevoir)}</span>
              <span className="stats-label">À recevoir</span>
              <span className="stats-detail">Encaissé {formatFcfa(tableau.montant_encaisse)}</span>
            </li>
          </ul>
          {tableau.montant_encaisse_annule > 0 ? (
            <p className="note">
              Encaissé sur un séjour annulé : {formatFcfa(tableau.montant_encaisse_annule)}.
              Cette somme est gardée à part, pour un remboursement éventuel.
            </p>
          ) : null}
        </>
      ) : null}

      <h2 className="sous-titre">Actions rapides</h2>
      <div className="actions-rapides">
        <button className="action" type="button" onClick={() => onAller('reservations', { action: 'creer' })}>
          <span className="action-icone"><IconeAjout /></span>
          <span>
            <strong>Nouvelle réservation</strong>
            <small>Dates, logement et acompte</small>
          </span>
        </button>
        <button className="action action-caramel" type="button" onClick={() => onAller('argent', { action: 'encaisser' })}>
          <span className="action-icone"><IconeArgent /></span>
          <span>
            <strong>Encaisser un paiement</strong>
            <small>L’argent vraiment reçu</small>
          </span>
        </button>
        <button className="action" type="button" onClick={synchroniserTout} disabled={synchro.enCours || chargement}>
          <span className="action-icone"><IconeSync /></span>
          <span>
            <strong>{synchro.enCours ? 'Synchronisation…' : 'Synchroniser Airbnb'}</strong>
            <small>Importer les séjours et les blocages</small>
          </span>
        </button>
      </div>
      {synchro.erreur ? <Alerte>{synchro.erreur}</Alerte> : null}
      {synchro.message ? <Alerte info>{synchro.message}</Alerte> : null}

      {lecture ? (
        <article className="carte carte-suite">
          <h2>E-mails Airbnb</h2>
          <p>{lecture.le ? `Dernière lecture : ${formaterMoment(lecture.le)}` : 'Pas encore de lecture.'}</p>
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
        </article>
      ) : null}

      {tableau && logements.length === 0 ? (
        <Vide
          titre="Aucun logement pour le moment"
          texte="Ajoutez le studio ou le chambre-salon pour commencer."
          action={(
            <button className="bouton" type="button" onClick={() => onAller('logements')}>
              Ajouter un logement
            </button>
          )}
        />
      ) : null}

      {logements.length > 0 ? (
        <>
          <h2 className="sous-titre">Prochaines arrivées</h2>
          {tableau && tableau.prochaines_arrivees.length === 0 ? (
            <Vide
              titre="Aucune arrivée à venir"
              texte="Les prochains séjours s’afficheront ici."
            />
          ) : null}
          {tableau && tableau.prochaines_arrivees.length > 0 ? (
            <ul className="cartes">
              {tableau.prochaines_arrivees.map((sejour) => (
                <LigneSejour key={sejour.id} sejour={sejour} etiquette="Arrivée" />
              ))}
            </ul>
          ) : null}

          <h2 className="sous-titre">Prochains départs</h2>
          {tableau && tableau.prochains_departs.length === 0 ? (
            <Vide titre="Aucun départ à venir" texte="Les départs des jours qui viennent s’afficheront ici." />
          ) : null}
          {tableau && tableau.prochains_departs.length > 0 ? (
            <ul className="cartes">
              {tableau.prochains_departs.map((sejour) => (
                <LigneSejour key={`depart-${sejour.id}`} sejour={sejour} etiquette="Départ" />
              ))}
            </ul>
          ) : null}
        </>
      ) : null}
    </section>
  )
}
