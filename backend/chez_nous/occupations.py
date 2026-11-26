from .rapports import MOIS

JOURS = (
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
)

STATUT_LIBRE = {
    "etat": "libre",
    "libelle": "Libre",
    "client_nom": "",
    "date_depart": None,
    "date_depart_libelle": "",
    "client_depart": "",
}


def date_fr(jour):
    return f"{jour.day} {MOIS[jour.month - 1]} {jour.year}"


def libelle_jour(jour):
    return f"{JOURS[jour.weekday()]} {date_fr(jour)}"


def _sejour(reservation):
    return {
        "id": str(reservation.id),
        "client_nom": reservation.client_nom,
        "logement_nom": reservation.logement.nom,
        "date_arrivee": reservation.date_arrivee.isoformat(),
        "date_depart": reservation.date_depart.isoformat(),
        "date_depart_libelle": date_fr(reservation.date_depart),
    }


def _statut_clients(sejours, jour):
    """Statut calculé sur les séjours, sans les blocages Airbnb."""
    arrivee = next(
        (reservation for reservation in sejours if reservation.date_arrivee == jour),
        None,
    )
    depart = next(
        (reservation for reservation in sejours if reservation.date_depart == jour),
        None,
    )
    occupant = next(
        (
            reservation
            for reservation in sejours
            if reservation.date_arrivee <= jour < reservation.date_depart
        ),
        None,
    )

    if arrivee and depart:
        return {
            "etat": "rotation",
            "libelle": (
                f"Départ de {depart.client_nom} et arrivée de {arrivee.client_nom}"
                f" · départ le {date_fr(arrivee.date_depart)}"
            ),
            "client_nom": arrivee.client_nom,
            "date_depart": arrivee.date_depart.isoformat(),
            "date_depart_libelle": date_fr(arrivee.date_depart),
            "client_depart": depart.client_nom,
        }
    if arrivee:
        return {
            "etat": "arrivee",
            "libelle": (
                f"Arrivée aujourd’hui · {arrivee.client_nom}"
                f" · départ le {date_fr(arrivee.date_depart)}"
            ),
            "client_nom": arrivee.client_nom,
            "date_depart": arrivee.date_depart.isoformat(),
            "date_depart_libelle": date_fr(arrivee.date_depart),
            "client_depart": "",
        }
    if depart:
        return {
            "etat": "depart",
            "libelle": f"Départ aujourd’hui · {depart.client_nom}",
            "client_nom": depart.client_nom,
            "date_depart": depart.date_depart.isoformat(),
            "date_depart_libelle": date_fr(depart.date_depart),
            "client_depart": depart.client_nom,
        }
    if occupant:
        return {
            "etat": "occupe",
            "libelle": (
                f"Occupé · {occupant.client_nom}"
                f" · départ le {date_fr(occupant.date_depart)}"
            ),
            "client_nom": occupant.client_nom,
            "date_depart": occupant.date_depart.isoformat(),
            "date_depart_libelle": date_fr(occupant.date_depart),
            "client_depart": "",
        }
    return dict(STATUT_LIBRE)


STATUT_BLOCAGE = {
    "etat": "blocage",
    "libelle": "Indisponible · Airbnb",
    "client_nom": "",
    "date_depart": None,
    "date_depart_libelle": "",
    "client_depart": "",
}


def statut_du_jour(reservations, jour):
    """Statut d'un logement pour une date, à partir de ses réservations actives.

    Le jour du départ n'est pas une nuit occupée. Une arrivée et un départ
    le même jour donnent une rotation : le nouveau client reste le soir.
    Un blocage Airbnb occupe les nuits sans être présenté comme un client.
    """
    actives = [reservation for reservation in reservations if not reservation.annulee]
    sejours = [reservation for reservation in actives if not reservation.blocage]
    blocages = [reservation for reservation in actives if reservation.blocage]
    statut = _statut_clients(sejours, jour)
    bloque_ce_soir = any(
        blocage.date_arrivee <= jour < blocage.date_depart for blocage in blocages
    )
    if not bloque_ce_soir or statut["etat"] not in {"libre", "depart"}:
        return statut
    if statut["etat"] == "depart":
        return {
            "etat": "blocage",
            "libelle": (
                f"Départ de {statut['client_depart']} · indisponible ensuite (Airbnb)"
            ),
            "client_nom": "",
            "date_depart": None,
            "date_depart_libelle": "",
            "client_depart": statut["client_depart"],
        }
    return dict(STATUT_BLOCAGE)


def _phrase(nb_logements, libres, occupes, arrivees, departs, indisponibles=0):
    """Résumé du jour.

    ``libres`` et ``occupes`` ne comptent que les logements sans mouvement
    aujourd’hui. Une arrivée ou un départ est annoncé à part, pour qu’un
    logement qui arrive aujourd’hui ne soit pas aussi qualifié d’occupé.
    """
    if nb_logements == 0:
        return "Aucun logement pour le moment."
    if occupes == 0 and arrivees == 0 and departs == 0 and indisponibles == 0:
        if nb_logements == 1:
            return "Aujourd’hui, le logement est libre."
        return f"Aujourd’hui, les {nb_logements} logements sont libres."
    if libres == 0 and arrivees == 0 and departs == 0 and indisponibles == 0:
        if nb_logements == 1:
            return "Aujourd’hui, le logement est occupé."
        return f"Aujourd’hui, les {nb_logements} logements sont occupés."

    morceaux = []
    if libres:
        morceaux.append(
            "1 logement libre" if libres == 1 else f"{libres} logements libres"
        )
    if occupes:
        morceaux.append("1 occupé" if occupes == 1 else f"{occupes} occupés")
    if arrivees:
        morceaux.append("1 arrivée" if arrivees == 1 else f"{arrivees} arrivées")
    if departs:
        morceaux.append("1 départ" if departs == 1 else f"{departs} départs")
    if indisponibles:
        morceaux.append(
            "1 indisponible" if indisponibles == 1 else f"{indisponibles} indisponibles"
        )
    return "Aujourd’hui : " + ", ".join(morceaux) + "."


def _prochains(reservations, attribut, jour, limite=3):
    choisis = [
        reservation
        for reservation in reservations
        if getattr(reservation, attribut) > jour
    ]
    choisis.sort(key=lambda reservation: (getattr(reservation, attribut), str(reservation.id)))
    return [_sejour(reservation) for reservation in choisis[:limite]]


def construire_tableau(logements, reservations, jour, finances):
    actives = [reservation for reservation in reservations if not reservation.annulee]
    sejours = [reservation for reservation in actives if not reservation.blocage]
    par_logement = {}
    for reservation in actives:
        par_logement.setdefault(reservation.logement_id, []).append(reservation)

    libres = occupes = arrivees = departs = indisponibles = 0
    disponibles = en_sejour = 0
    for logement in logements:
        statut = statut_du_jour(par_logement.get(logement.id, []), jour)
        etat = statut["etat"]
        if etat == "libre":
            libres += 1
            disponibles += 1
        elif etat == "occupe":
            occupes += 1
            en_sejour += 1
        elif etat == "arrivee":
            arrivees += 1
            en_sejour += 1
        elif etat == "depart":
            departs += 1
            disponibles += 1
        elif etat == "rotation":
            arrivees += 1
            departs += 1
            en_sejour += 1
        elif etat == "blocage":
            indisponibles += 1
            if statut["client_depart"]:
                departs += 1

    arrivees_jour = [_sejour(reservation) for reservation in sejours if reservation.date_arrivee == jour]
    departs_jour = [_sejour(reservation) for reservation in sejours if reservation.date_depart == jour]
    arrivees_jour.sort(key=lambda item: (item["logement_nom"], item["id"]))
    departs_jour.sort(key=lambda item: (item["logement_nom"], item["id"]))

    return {
        "date": jour.isoformat(),
        "libelle_date": libelle_jour(jour),
        "phrase": _phrase(len(logements), libres, occupes, arrivees, departs, indisponibles),
        "logements_libres": disponibles,
        "logements_occupes": en_sejour,
        "arrivees_aujourdhui": arrivees_jour,
        "departs_aujourdhui": departs_jour,
        "prochaines_arrivees": _prochains(sejours, "date_arrivee", jour),
        "prochains_departs": _prochains(sejours, "date_depart", jour),
        **finances,
    }
