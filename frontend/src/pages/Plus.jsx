import { useEffect, useState } from 'react'
import Calendrier from './Calendrier.jsx'
import Rapports from './Rapports.jsx'

export default function Plus({ onChoisirLogement }) {
  const [ecran, setEcran] = useState(null)

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [ecran])

  if (ecran === 'calendrier') {
    return (
      <Calendrier
        onChoisirLogement={onChoisirLogement}
        onRetour={() => setEcran(null)}
      />
    )
  }

  if (ecran === 'rapports') {
    return <Rapports onRetour={() => setEcran(null)} />
  }

  return (
    <section className="page">
      <h1>Plus</h1>
      <p className="chapo">Le calendrier pendant un appel, et les bilans de la semaine ou du mois.</p>
      <ul className="menu">
        <li>
          <button type="button" onClick={() => setEcran('calendrier')}>
            <strong>Calendrier</strong>
            <span>Voir quel logement est libre, puis réserver</span>
          </button>
        </li>
        <li>
          <button type="button" onClick={() => setEcran('rapports')}>
            <strong>Rapports</strong>
            <span>Occupation, encaissements et dépenses</span>
          </button>
        </li>
      </ul>
    </section>
  )
}
