async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  })
  const text = await response.text()
  const data = text ? JSON.parse(text) : null
  if (!response.ok) {
    const error = new Error(`Réponse ${response.status}`)
    error.details = data
    throw error
  }
  return data
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

export function getReservations() {
  return requestJson('/api/reservations/')
}

export function createReservation(reservation) {
  return requestJson('/api/reservations/', {
    method: 'POST',
    body: JSON.stringify(reservation),
  })
}

export function getDisponibilites(arrivee, depart) {
  const params = new URLSearchParams({ arrivee, depart })
  return requestJson(`/api/disponibilites/?${params}`)
}

export function getSynthese() {
  return requestJson('/api/synthese/')
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
