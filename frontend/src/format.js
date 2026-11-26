const MOIS = [
  'janv.',
  'févr.',
  'mars',
  'avr.',
  'mai',
  'juin',
  'juil.',
  'août',
  'sept.',
  'oct.',
  'nov.',
  'déc.',
]

export function formatDate(iso) {
  if (!iso) {
    return ''
  }
  const morceau = String(iso).slice(0, 10)
  const [annee, mois, jour] = morceau.split('-').map(Number)
  if (!annee || !mois || !jour) {
    return String(iso)
  }
  return `${jour} ${MOIS[mois - 1]} ${annee}`
}

export function formatPlage(arrivee, depart) {
  return `${formatDate(arrivee)} → ${formatDate(depart)}`
}

export function aujourdhui() {
  const date = new Date()
  const mois = String(date.getMonth() + 1).padStart(2, '0')
  const jour = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${mois}-${jour}`
}

export function formaterMoment(iso) {
  if (!iso) {
    return ''
  }
  return new Date(iso).toLocaleString('fr-FR', {
    timeZone: 'Africa/Lome',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function messageErreur(error, secours = 'Enregistrement impossible.') {
  const details = error?.details
  if (!details || typeof details !== 'object') {
    return secours
  }
  if (typeof details.detail === 'string') {
    return details.detail
  }
  const textes = Object.values(details)
    .flat()
    .filter((valeur) => typeof valeur === 'string')
  return textes[0] || secours
}

export function capitale(texte) {
  if (!texte) {
    return ''
  }
  return texte.charAt(0).toUpperCase() + texte.slice(1)
}
