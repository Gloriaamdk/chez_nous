export function Maison({ className = 'maison' }) {
  return (
    <svg className={className} viewBox="0 0 80 64" fill="none" aria-hidden="true">
      <path
        d="M8 58 V30 L40 8 L72 30 V58"
        stroke="currentColor"
        strokeWidth="3.2"
        strokeLinejoin="miter"
        strokeLinecap="butt"
      />
      <g fill="#C08A55">
        <rect x="35.2" y="22" width="3.6" height="3.6" />
        <rect x="40.6" y="22" width="3.6" height="3.6" />
        <rect x="35.2" y="27.4" width="3.6" height="3.6" />
        <rect x="40.6" y="27.4" width="3.6" height="3.6" />
      </g>
    </svg>
  )
}

export function LogoComplet() {
  return (
    <div className="logo-complet" role="img" aria-label="Chez Nous. Feel at home.">
      <Maison />
      <p className="logo-chez">Chez</p>
      <p className="logo-nous">nous</p>
      <p className="logo-filet" aria-hidden="true">
        <span />
        <i />
        <span />
      </p>
      <p className="logo-slogan">Feel at home</p>
    </div>
  )
}

export function Marque() {
  return (
    <div className="marque">
      <img src="/logo-mark.svg" alt="" width="40" height="40" />
      <p className="marque-nom">
        Chez <span className="nous">nous</span>
      </p>
    </div>
  )
}

function Icone({ children }) {
  return (
    <svg className="icone" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      {children}
    </svg>
  )
}

const trait = {
  stroke: 'currentColor',
  strokeWidth: 1.7,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
}

export function IconeAccueil() {
  return (
    <Icone>
      <path d="M4 10.8 12 4.2 20 10.8V20a1 1 0 0 1-1 1h-4.2v-5.5h-5.6V21H5a1 1 0 0 1-1-1z" {...trait} />
    </Icone>
  )
}

export function IconeReservations() {
  return (
    <Icone>
      <rect x="4" y="5" width="16" height="15" rx="2" {...trait} />
      <path d="M8 3.5v3.2M16 3.5v3.2M4 10h16" {...trait} />
    </Icone>
  )
}

export function IconeLogements() {
  return (
    <Icone>
      <path d="M4.5 20V8.2L12 4.5l7.5 3.7V20" {...trait} />
      <path d="M9.5 20v-4.2h5V20" {...trait} />
      <path d="M9 10.2h.01M12 10.2h.01M15 10.2h.01M9 13.6h.01M12 13.6h.01M15 13.6h.01" {...trait} />
    </Icone>
  )
}

export function IconeArgent() {
  return (
    <Icone>
      <rect x="3" y="6" width="18" height="13" rx="2" {...trait} />
      <path d="M3 10.2h18" {...trait} />
      <circle cx="12" cy="14.4" r="1.5" {...trait} />
    </Icone>
  )
}

export function IconePlus() {
  return (
    <Icone>
      <circle cx="6" cy="12" r="1.35" fill="currentColor" />
      <circle cx="12" cy="12" r="1.35" fill="currentColor" />
      <circle cx="18" cy="12" r="1.35" fill="currentColor" />
    </Icone>
  )
}

export function IconeAjout() {
  return (
    <Icone>
      <path d="M12 5.5v13M5.5 12h13" {...trait} />
    </Icone>
  )
}

export function IconeSync() {
  return (
    <Icone>
      <path d="M20 12a8 8 0 0 1-13.5 5.8" {...trait} />
      <path d="M4 12a8 8 0 0 1 13.5-5.8" {...trait} />
      <path d="M16.2 4.2H18V6.8M7.8 19.8H6V17.2" {...trait} />
    </Icone>
  )
}

const CANAUX = {
  airbnb: 'badge-airbnb',
  whatsapp: 'badge-whatsapp',
  telephone: 'badge-telephone',
}

export function BadgeCanal({ canal, libelle }) {
  return <span className={`badge ${CANAUX[canal] || 'badge-telephone'}`}>{libelle}</span>
}

export function PastilleStatut({ etat, libelle }) {
  const classe = etat === 'libre'
    ? 'statut-libre'
    : etat === 'occupe' || etat === 'blocage'
      ? 'statut-occupe'
      : 'statut-mouvement'
  return <p className={`statut ${classe}`}>{libelle}</p>
}

export function Vide({ titre, texte, action }) {
  return (
    <div className="vide">
      <Maison />
      <p className="vide-titre">{titre}</p>
      {texte ? <p>{texte}</p> : null}
      {action || null}
    </div>
  )
}

export function Chargement({ texte = 'Chargement…' }) {
  return (
    <p className="chargement" role="status">
      <span className="chargement-piste" aria-hidden="true" />
      {texte}
    </p>
  )
}

export function Alerte({ children, info = false }) {
  return (
    <p className={info ? 'alerte alerte-info' : 'alerte'} role={info ? 'status' : 'alert'}>
      {children}
    </p>
  )
}
