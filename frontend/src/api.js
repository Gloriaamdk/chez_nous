let signalerSessionExpiree = () => {}

export function definirGestionnaireSession(gestionnaire) {
  signalerSessionExpiree = gestionnaire
}

function lireJetonCsrf() {
  const correspondance = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/)
  return correspondance ? decodeURIComponent(correspondance[1]) : ''
}

async function requestJson(url, options = {}) {
  const { gererSession = true, headers: enTetes = {}, ...requete } = options
  const headers = {
    Accept: 'application/json',
    ...(requete.body ? { 'Content-Type': 'application/json' } : {}),
    ...enTetes,
  }
  const jeton = lireJetonCsrf()
  if (jeton) {
    headers['X-CSRFToken'] = jeton
  }

  let response
  try {
    response = await fetch(url, {
      ...requete,
      credentials: 'include',
      headers,
    })
  } catch {
    const error = new Error('Le serveur ne répond pas.')
    error.status = 0
    throw error
  }

  const text = await response.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = null
    }
  }
  const detail = data && typeof data.detail === 'string' ? data.detail : ''
  const sessionAbsente =
    response.status === 401 || (response.status === 403 && detail === 'Connexion requise.')
  if (sessionAbsente && gererSession) {
    signalerSessionExpiree()
  }
  if (!response.ok) {
    const error = new Error(`Réponse ${response.status}`)
    error.status = response.status
    error.details = data
    throw error
  }
  return data
}

export function preparerCsrf() {
  return requestJson('/api/auth/csrf/', { gererSession: false })
}

export function getMoi() {
  return requestJson('/api/auth/moi/', { gererSession: false })
}

export async function connecter(identifiant, motDePasse) {
  await preparerCsrf()
  return requestJson('/api/auth/connexion/', {
    method: 'POST',
    gererSession: false,
    body: JSON.stringify({
      identifiant,
      mot_de_passe: motDePasse,
    }),
  })
}

export function deconnecter() {
  return requestJson('/api/auth/deconnexion/', { method: 'POST' })
}

export function getStatus() {
  return requestJson('/api/status/')
}

export function getReferentiels() {
  return requestJson('/api/referentiels/')
}

export function getLogements() {
  return requestJson('/api/logements/')
}

export function createLogement(logement) {
  return requestJson('/api/logements/', {
    method: 'POST',
    body: JSON.stringify(logement),
  })
}

export function updateLogement(id, logement) {
  return requestJson(`/api/logements/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(logement),
  })
}

export function synchroniserAirbnb(id) {
  return requestJson(`/api/logements/${id}/synchroniser/`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function nouveauLienIcal(id) {
  return requestJson(`/api/logements/${id}/nouveau-lien-ical/`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function getLectureEmails() {
  return requestJson('/api/airbnb/lecture/')
}

export function lienAbsolu(chemin) {
  if (!chemin) {
    return ''
  }
  return new URL(chemin, window.location.origin).href
}

export function getReservations() {
  return requestJson('/api/reservations/')
}

export function createReservation(reservation) {
  return requestJson('/api/reservations/', {
    method: 'POST',
    body: JSON.stringify(reservation),
  })
}

export function updateReservation(id, reservation) {
  return requestJson(`/api/reservations/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(reservation),
  })
}

export function annulerReservation(id) {
  return requestJson(`/api/reservations/${id}/annuler/`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function getDisponibilites(arrivee, depart) {
  const params = new URLSearchParams({ arrivee, depart })
  return requestJson(`/api/disponibilites/?${params}`)
}

export function getSynthese() {
  return requestJson('/api/synthese/')
}

export function getTableauDeBord() {
  return requestJson('/api/tableau-de-bord/')
}

export function getPaiements() {
  return requestJson('/api/paiements/')
}

export function createPaiement(paiement) {
  return requestJson('/api/paiements/', {
    method: 'POST',
    body: JSON.stringify(paiement),
  })
}

export function getDepenses() {
  return requestJson('/api/depenses/')
}

export function createDepense(depense) {
  return requestJson('/api/depenses/', {
    method: 'POST',
    body: JSON.stringify(depense),
  })
}

export function getRapport(periode, date) {
  const params = new URLSearchParams({ periode })
  if (date) {
    params.set('date', date)
  }
  return requestJson(`/api/rapports/?${params}`)
}

export function formatFcfa(montant) {
  return `${new Intl.NumberFormat('fr-FR').format(montant)} FCFA`
}
