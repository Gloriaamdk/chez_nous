from datetime import timedelta

MOIS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def bornes_semaine(jour):
    debut = jour - timedelta(days=jour.weekday())
    return debut, debut + timedelta(days=7)


def bornes_mois(jour):
    debut = jour.replace(day=1)
    if debut.month == 12:
        fin = debut.replace(year=debut.year + 1, month=1)
    else:
        fin = debut.replace(month=debut.month + 1)
    return debut, fin


def _libelle_jour(jour):
    return f"{jour.day} {MOIS[jour.month - 1]} {jour.year}"


def libelle_periode(periode, debut, fin):
    if periode == "mois":
        return f"{MOIS[debut.month - 1]} {debut.year}"
    dernier = fin - timedelta(days=1)
    if debut.month == dernier.month and debut.year == dernier.year:
        return f"Semaine du {debut.day} au {_libelle_jour(dernier)}"
    return f"Semaine du {_libelle_jour(debut)} au {_libelle_jour(dernier)}"


def nuits_communes(arrivee, depart, debut, fin):
    debut_commun = max(arrivee, debut)
    fin_commune = min(depart, fin)
    if fin_commune <= debut_commun:
        return 0
    return (fin_commune - debut_commun).days


def _taux(occupees, possibles):
    if not possibles:
        return 0
    return round(occupees * 100 / possibles)


def _ligne(nuits_occupees, nuits_possibles, encaissements, depenses):
    return {
        "nuits_occupees": nuits_occupees,
        "nuits_possibles": nuits_possibles,
        "taux_occupation": _taux(nuits_occupees, nuits_possibles),
        "encaissements": encaissements,
        "depenses": depenses,
    }


def _ecart(actuel, precedent):
    return {
        "nuits_occupees": actuel["nuits_occupees"] - precedent["nuits_occupees"],
        "taux_occupation": actuel["taux_occupation"] - precedent["taux_occupation"],
        "encaissements": actuel["encaissements"] - precedent["encaissements"],
        "depenses": actuel["depenses"] - precedent["depenses"],
    }


def _indicateurs(logements, reservations, paiements, depenses, debut, fin):
    nuits_periode = (fin - debut).days
    lignes = []
    for logement in logements:
        nuits = sum(
            nuits_communes(reservation.date_arrivee, reservation.date_depart, debut, fin)
            for reservation in reservations
            if reservation.logement_id == logement.id
        )
        encaisse = sum(
            paiement.montant
            for paiement in paiements
            if paiement.reservation.logement_id == logement.id and debut <= paiement.date < fin
        )
        sorties = sum(
            depense.montant
            for depense in depenses
            if depense.logement_id == logement.id and debut <= depense.date < fin
        )
        lignes.append(
            {
                "id": str(logement.id),
                "nom": logement.nom,
                **_ligne(nuits, nuits_periode, encaisse, sorties),
            }
        )
    total = _ligne(
        sum(ligne["nuits_occupees"] for ligne in lignes),
        nuits_periode * len(logements),
        sum(ligne["encaissements"] for ligne in lignes),
        sum(ligne["depenses"] for ligne in lignes),
    )
    return lignes, total


def construire_rapport(logements, reservations, paiements, depenses, periode, jour):
    if periode == "semaine":
        debut, fin = bornes_semaine(jour)
        precedent_jour = debut - timedelta(days=1)
        prec_debut, prec_fin = bornes_semaine(precedent_jour)
    elif periode == "mois":
        debut, fin = bornes_mois(jour)
        prec_debut, prec_fin = bornes_mois(debut - timedelta(days=1))
    else:
        raise ValueError(periode)

    lignes, total = _indicateurs(logements, reservations, paiements, depenses, debut, fin)
    prec_lignes, prec_total = _indicateurs(
        logements, reservations, paiements, depenses, prec_debut, prec_fin
    )
    precedent_par_id = {ligne["id"]: ligne for ligne in prec_lignes}

    def avec_comparaison(ligne, precedent):
        return {
            **ligne,
            "precedent": precedent,
            "ecart": _ecart(ligne, precedent),
        }

    return {
        "periode": periode,
        "libelle": libelle_periode(periode, debut, fin),
        "debut": debut,
        "fin": fin,
        "precedente": {
            "libelle": libelle_periode(periode, prec_debut, prec_fin),
            "debut": prec_debut,
            "fin": prec_fin,
        },
        "total": avec_comparaison(total, prec_total),
        "logements": [
            avec_comparaison(ligne, precedent_par_id[ligne["id"]]) for ligne in lignes
        ],
    }
