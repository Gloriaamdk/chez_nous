"""Calendriers Airbnb, dans les deux sens, via les fichiers iCal.

Airbnb ne propose pas d’API aux petits hôtes. L’hôte copie le lien d’export
iCal de l’annonce : on en fait des réservations et des blocages. Dans l’autre
sens, on publie un calendrier sans nom de client, que l’hôte colle dans
Airbnb pour bloquer les nuits déjà prises par WhatsApp ou par téléphone.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from icalendar import Calendar, Event

from .models import MESSAGE_LOGEMENT_OCCUPE, Reservation

NOM_CLIENT = "Client Airbnb"
NOM_BLOCAGE = "Indisponible Airbnb"
NOMS_DEFAUT = {NOM_CLIENT, NOM_BLOCAGE}
TELEPHONE_A_COMPLETER = "À compléter"
RESUME_EXPORT = "Réservé"
MESSAGE_URL = (
    "Collez le lien d’export iCal fourni par Airbnb "
    "(une adresse https vers airbnb.com)."
)
TAILLE_MAX = 2_000_000
DELAI_SECONDES = 20

_HOTE_AIRBNB = re.compile(
    r"^(?:[a-z0-9-]+\.)*airbnb\.(?:[a-z]{2,3}|co\.[a-z]{2})$",
    re.IGNORECASE,
)
_BLOCAGE = ("not available", "unavailable", "blocked", "blocage", "indisponible")


class ErreurCalendrier(Exception):
    """Le flux Airbnb n’a pas pu être lu. Les séjours déjà enregistrés restent."""


_CODE_ICAL = re.compile(r"\b(HM[A-Z0-9]{6,10})\b", re.IGNORECASE)
_CODE_URL = re.compile(
    r"(?:code|confirmation)[=/]([A-Z0-9]{6,12})",
    re.IGNORECASE,
)


def extraire_code(*textes):
    """Code de confirmation Airbnb présent dans une description ou une adresse."""
    for texte in textes:
        if not texte:
            continue
        trouve = _CODE_ICAL.search(str(texte)) or _CODE_URL.search(str(texte))
        if trouve:
            return trouve.group(1).upper()
    return ""


@dataclass(frozen=True)
class EvenementIcal:
    uid: str
    arrivee: date | None
    depart: date | None
    blocage: bool
    resume: str
    message: str = ""
    code: str = ""

    @property
    def valide(self):
        return (
            bool(self.uid)
            and self.arrivee is not None
            and self.depart is not None
            and self.depart > self.arrivee
            and not self.message
        )


def url_airbnb_valide(url):
    if not isinstance(url, str):
        return False
    try:
        morceaux = urlsplit(url.strip())
    except ValueError:
        return False
    if morceaux.scheme != "https" or morceaux.username or morceaux.password:
        return False
    hote = (morceaux.hostname or "").rstrip(".")
    return bool(hote) and _HOTE_AIRBNB.fullmatch(hote) is not None


def resultat_vide():
    return {
        "creees": 0,
        "modifiees": 0,
        "annulees": 0,
        "conflits": [],
        "erreur": "",
        "resume": "",
    }


def accord(nombre, singulier, pluriel):
    return f"{nombre} {singulier if nombre == 1 else pluriel}"


def phrase_resultat(resultat):
    if resultat.get("erreur"):
        return resultat["erreur"]
    return (
        f"{accord(resultat['creees'], 'créée', 'créées')}, "
        f"{accord(resultat['modifiees'], 'modifiée', 'modifiées')}, "
        f"{accord(resultat['annulees'], 'annulée', 'annulées')}, "
        f"{accord(len(resultat['conflits']), 'conflit', 'conflits')}."
    )


def phrase_conflit(conflit):
    resume = conflit.get("resume") or "Événement Airbnb"
    arrivee = conflit.get("arrivee") or ""
    depart = conflit.get("depart") or ""
    quand = f", du {arrivee} au {depart}" if arrivee and depart else ""
    return f"{resume}{quand} : {conflit.get('message', '')}"


def est_blocage(resume):
    texte = (resume or "").casefold()
    return any(mot in texte for mot in _BLOCAGE)


def nom_pour(evenement):
    return NOM_BLOCAGE if evenement.blocage else NOM_CLIENT


def _en_date(valeur):
    if valeur is None:
        return None
    brut = getattr(valeur, "dt", valeur)
    if isinstance(brut, datetime):
        if brut.tzinfo is not None:
            brut = timezone.localtime(brut)
        return brut.date()
    if isinstance(brut, date):
        return brut
    return None


def _texte(composant, nom):
    valeur = composant.get(nom)
    if valeur is None:
        return ""
    return str(valeur).strip()


def interpreter_evenement(composant):
    uid = _texte(composant, "uid")
    resume = _texte(composant, "summary")
    arrivee = _en_date(composant.get("dtstart"))
    depart = _en_date(composant.get("dtend"))
    message = ""
    if not uid:
        message = "Cet événement Airbnb n’a pas d’identifiant. Il a été ignoré."
    elif len(uid) > 255:
        message = "Cet événement Airbnb a un identifiant trop long. Il a été ignoré."
        uid = uid[:255]
    elif arrivee is None or depart is None:
        message = "Cet événement Airbnb a des dates illisibles. Il a été ignoré."
    elif depart <= arrivee:
        message = "Cet événement Airbnb a un départ qui n’est pas après l’arrivée. Il a été ignoré."
    return EvenementIcal(
        uid=uid,
        arrivee=arrivee,
        depart=depart,
        blocage=est_blocage(resume),
        resume=resume or "Événement Airbnb",
        code=extraire_code(_texte(composant, "description"), _texte(composant, "url")),
        message=message,
    )


def lire_evenements(contenu):
    if isinstance(contenu, str):
        contenu = contenu.encode("utf-8")
    try:
        calendriers = Calendar.from_ical(contenu, multiple=True)
    except Exception as exc:
        raise ErreurCalendrier("Ce fichier n’est pas un calendrier lisible.") from exc
    evenements = []
    for calendrier in calendriers:
        if not hasattr(calendrier, "walk"):
            continue
        for composant in calendrier.walk("VEVENT"):
            evenements.append(interpreter_evenement(composant))
    return evenements


def libelle_evenement(evenement):
    """Libellé français. Le flux Airbnb dit « Reserved » ou « Not available »."""
    if evenement is None:
        return "Événement Airbnb"
    if evenement.blocage or est_blocage(evenement.resume):
        return "Blocage Airbnb"
    return "Séjour Airbnb"


def _conflit(evenement, message, uid=None):
    arrivee = evenement.arrivee.isoformat() if evenement and evenement.arrivee else ""
    depart = evenement.depart.isoformat() if evenement and evenement.depart else ""
    return {
        "uid": uid if uid is not None else (evenement.uid if evenement else ""),
        "resume": libelle_evenement(evenement),
        "arrivee": arrivee,
        "depart": depart,
        "message": message,
    }


def _message_validation(exc):
    messages = getattr(exc, "messages", None)
    if messages:
        return " ".join(str(message) for message in messages)
    return MESSAGE_LOGEMENT_OCCUPE


def _enregistrer_resultat(logement, resultat):
    resultat["resume"] = phrase_resultat(resultat)
    logement.synchro_le = timezone.now()
    logement.synchro_resultat = resultat
    logement.save(update_fields=["synchro_le", "synchro_resultat"])


def _annuler(reservation):
    reservation.annulee = True
    reservation.annulee_le = timezone.localdate()
    reservation.save()


def _creer(logement, evenement):
    reservation = Reservation(
        logement=logement,
        client_nom=nom_pour(evenement),
        client_telephone=TELEPHONE_A_COMPLETER,
        canal=Reservation.Canal.AIRBNB,
        mode=Reservation.Mode.NUITEE,
        date_arrivee=evenement.arrivee,
        date_depart=evenement.depart,
        montant_prevu=0,
        uid_ical=evenement.uid,
        blocage=evenement.blocage,
        code_airbnb=evenement.code,
    )
    reservation.save()
    return reservation


def _mettre_a_jour(reservation, evenement):
    """Met à jour les dates. Le nom et le prix déjà saisis par Gloria restent."""
    avant = (
        reservation.date_arrivee,
        reservation.date_depart,
        reservation.mode,
        reservation.montant_prevu,
    )
    changements = False
    if reservation.annulee:
        reservation.annulee = False
        reservation.annulee_le = None
        changements = True
    if reservation.date_arrivee != evenement.arrivee:
        reservation.date_arrivee = evenement.arrivee
        changements = True
    if reservation.date_depart != evenement.depart:
        reservation.date_depart = evenement.depart
        changements = True
    if reservation.blocage != evenement.blocage:
        reservation.blocage = evenement.blocage
        changements = True
    nom = nom_pour(evenement)
    if reservation.client_nom in NOMS_DEFAUT and reservation.client_nom != nom:
        reservation.client_nom = nom
        changements = True
    if not reservation.client_telephone:
        reservation.client_telephone = TELEPHONE_A_COMPLETER
        changements = True
    if reservation.canal != Reservation.Canal.AIRBNB:
        reservation.canal = Reservation.Canal.AIRBNB
        changements = True
    if reservation.uid_ical != evenement.uid:
        reservation.uid_ical = evenement.uid
        changements = True
    if evenement.code and not reservation.code_airbnb:
        reservation.code_airbnb = evenement.code
        changements = True
    if evenement.blocage and reservation.montant_prevu != 0:
        reservation.montant_prevu = 0
        changements = True
    if not changements:
        return False

    reservation.save()
    calendrier_change = avant != (
        reservation.date_arrivee,
        reservation.date_depart,
        reservation.mode,
        reservation.montant_prevu,
    )
    if reservation.blocage:
        reservation.echeances.all().delete()
    elif calendrier_change:
        if reservation.montant_prevu:
            reservation.generer_echeances()
        else:
            reservation.echeances.all().delete()
    return True


def _orphelin_pour(orphelins, evenement):
    """Séjour créé par un e-mail, pas encore relié à un événement iCal.

    Le code de confirmation prime. Sinon, les mêmes dates sur ce logement.
    Deux codes différents ne sont jamais fusionnés.
    """
    if evenement.code:
        par_code = [
            reservation
            for reservation in orphelins
            if reservation.code_airbnb == evenement.code
        ]
        if len(par_code) == 1:
            return par_code[0]
        if len(par_code) > 1:
            return None
    memes_dates = [
        reservation
        for reservation in orphelins
        if reservation.date_arrivee == evenement.arrivee
        and reservation.date_depart == evenement.depart
        and (
            not reservation.code_airbnb
            or not evenement.code
            or reservation.code_airbnb == evenement.code
        )
    ]
    if len(memes_dates) == 1:
        return memes_dates[0]
    return None


def appliquer_flux(logement, evenements):
    """Crée, met à jour ou annule les séjours liés aux UID du flux.

    Un conflit de nuits est noté et n’empêche pas le reste du flux.
    Les réservations sans UID (saisies à la main) ne sont pas annulées.
    """
    resultat = resultat_vide()
    par_uid = {}
    for evenement in evenements:
        if not evenement.valide:
            resultat["conflits"].append(_conflit(evenement, evenement.message))
            continue
        par_uid[evenement.uid] = evenement

    sejours = list(Reservation.objects.filter(logement=logement))
    existantes = {
        reservation.uid_ical: reservation
        for reservation in sejours
        if reservation.uid_ical
    }
    orphelins = [
        reservation
        for reservation in sejours
        if not reservation.uid_ical
        and reservation.canal == Reservation.Canal.AIRBNB
        and not reservation.blocage
    ]
    for uid, evenement in par_uid.items():
        if uid in existantes or evenement.blocage:
            continue
        candidat = _orphelin_pour(orphelins, evenement)
        if candidat is None:
            continue
        existantes[uid] = candidat
        orphelins.remove(candidat)

    for uid, reservation in existantes.items():
        if uid in par_uid or reservation.annulee:
            continue
        try:
            with transaction.atomic():
                _annuler(reservation)
            resultat["annulees"] += 1
        except ValidationError as exc:
            resultat["conflits"].append(
                {
                    "uid": uid,
                    "resume": reservation.client_nom,
                    "arrivee": reservation.date_arrivee.isoformat(),
                    "depart": reservation.date_depart.isoformat(),
                    "message": _message_validation(exc),
                }
            )

    for uid, evenement in par_uid.items():
        if uid not in existantes:
            continue
        try:
            with transaction.atomic():
                if _mettre_a_jour(existantes[uid], evenement):
                    resultat["modifiees"] += 1
        except ValidationError as exc:
            resultat["conflits"].append(_conflit(evenement, _message_validation(exc)))

    for uid, evenement in par_uid.items():
        if uid in existantes:
            continue
        try:
            with transaction.atomic():
                _creer(logement, evenement)
            resultat["creees"] += 1
        except ValidationError as exc:
            resultat["conflits"].append(_conflit(evenement, _message_validation(exc)))

    return resultat


def recuperer_flux(url):
    if not url_airbnb_valide(url):
        raise ErreurCalendrier(MESSAGE_URL)
    requete = Request(
        url.strip(),
        headers={
            "User-Agent": "ChezNous/1.0",
            "Accept": "text/calendar, text/plain;q=0.9, */*;q=0.1",
        },
    )
    try:
        with urlopen(requete, timeout=DELAI_SECONDES) as reponse:
            adresse_finale = reponse.geturl()
            if not url_airbnb_valide(adresse_finale):
                raise ErreurCalendrier(
                    "Le calendrier Airbnb a renvoyé une adresse inattendue."
                )
            donnees = reponse.read(TAILLE_MAX + 1)
    except ErreurCalendrier:
        raise
    except HTTPError as exc:
        raise ErreurCalendrier(
            "Airbnb n’a pas renvoyé le calendrier. Vérifiez le lien d’export."
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ErreurCalendrier(
            "Le calendrier Airbnb est injoignable pour le moment."
        ) from exc
    if len(donnees) > TAILLE_MAX:
        raise ErreurCalendrier("Le calendrier Airbnb est trop volumineux.")
    if not donnees:
        raise ErreurCalendrier("Airbnb a renvoyé un calendrier vide.")
    return donnees


def synchroniser_logement(logement, contenu=None):
    """Lit le flux du logement et enregistre le résultat, sans lever l’erreur de lecture.

    ``contenu`` sert aux tests : aucun appel réseau n’est fait quand il est fourni.
    Une erreur de lecture n’annule aucun séjour.
    """
    if contenu is None and not (logement.url_ical_airbnb or "").strip():
        raise ErreurCalendrier("Indiquez d’abord l’adresse du calendrier Airbnb.")
    try:
        if contenu is None:
            contenu = recuperer_flux(logement.url_ical_airbnb)
        resultat = appliquer_flux(logement, lire_evenements(contenu))
    except ErreurCalendrier as exc:
        resultat = resultat_vide()
        resultat["erreur"] = str(exc)
    _enregistrer_resultat(logement, resultat)
    return resultat


def construire_ical(logement):
    """Calendrier public : nuits des autres canaux, sans donnée personnelle."""
    calendrier = Calendar()
    calendrier.add("prodid", "-//Chez Nous//Calendrier//FR")
    calendrier.add("version", "2.0")
    calendrier.add("calscale", "GREGORIAN")
    calendrier.add("method", "PUBLISH")
    calendrier.add("x-wr-calname", logement.nom)
    sejours = (
        logement.reservations.filter(annulee=False, blocage=False)
        .exclude(canal=Reservation.Canal.AIRBNB)
        .order_by("date_arrivee", "id")
    )
    maintenant = timezone.now()
    for reservation in sejours:
        evenement = Event()
        evenement.add("uid", f"{reservation.id}@chez-nous")
        evenement.add("summary", RESUME_EXPORT)
        evenement.add("dtstart", reservation.date_arrivee)
        evenement.add("dtend", reservation.date_depart)
        evenement.add("dtstamp", maintenant)
        calendrier.add_component(evenement)
    return calendrier.to_ical()
