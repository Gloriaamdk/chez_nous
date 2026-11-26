"""Applique les e-mails Airbnb aux réservations, sans garder leur texte.

La connexion IMAP est en lecture seule : aucun message n’est supprimé ni marqué.
Les tests passent les messages déjà lus et n’ouvrent pas de connexion.
"""

import imaplib
from datetime import timedelta
from email import policy
from email.parser import BytesParser

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .airbnb import NOM_CLIENT, TELEPHONE_A_COMPLETER, accord
from .emails_airbnb import analyser_email, normaliser, texte_du_message
from .models import (
    MESSAGE_LOGEMENT_OCCUPE,
    LectureEmails,
    Logement,
    MessageEmailTraite,
    Reservation,
)

JOURS_RETRO = 30
MESSAGES_MAX = 80
_MOIS_IMAP = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


class ErreurLecture(Exception):
    """La boîte mail n’a pas pu être lue. Les séjours déjà enregistrés restent."""


def phrase_lecture(resultat):
    if resultat.get("erreur"):
        return resultat["erreur"]
    if resultat.get("rien_de_nouveau"):
        return "Aucun nouvel e-mail."
    return (
        f"{accord(resultat['creees'], 'créée', 'créées')}, "
        f"{accord(resultat['completees'], 'complétée', 'complétées')}, "
        f"{accord(resultat['modifiees'], 'modifiée', 'modifiées')}, "
        f"{accord(resultat['annulees'], 'annulée', 'annulées')}."
    )


def resultat_lecture_vide():
    return {
        "creees": 0,
        "completees": 0,
        "modifiees": 0,
        "annulees": 0,
        "ignorees": 0,
        "notes": [],
        "erreur": "",
        "resume": "",
        "rien_de_nouveau": False,
    }


def configuration_imap():
    return settings.AIRBNB_IMAP


def imap_configure():
    config = configuration_imap()
    return bool(config.get("hote") and config.get("utilisateur") and config.get("mot_de_passe"))


def _date_imap(jour):
    return f"{jour.day:02d}-{_MOIS_IMAP[jour.month - 1]}-{jour.year}"


def _ouvrir_imap(config):
    return imaplib.IMAP4_SSL(config["hote"], int(config.get("port") or 993), timeout=30)


def _corps_fetch(reponse):
    if not reponse:
        return b""
    for element in reponse:
        if isinstance(element, tuple) and len(element) >= 2 and isinstance(element[1], (bytes, bytearray)):
            return bytes(element[1])
    return b""


def _entete(brut):
    message = BytesParser(policy=policy.default).parsebytes(brut or b"")
    return str(message.get("from") or ""), str(message.get("message-id") or "").strip()


def expediteur_autorise(entete, autorises):
    texte = (entete or "").casefold()
    return any(adresse.casefold() in texte for adresse in autorises if adresse)


def lire_boite(config=None, ouvrir=None):
    """Lit les messages récents des expéditeurs autorisés, sans les modifier."""
    config = config or configuration_imap()
    if not config.get("hote") or not config.get("utilisateur") or not config.get("mot_de_passe"):
        raise ErreurLecture(
            "La lecture des e-mails n’est pas configurée. "
            "Renseignez la boîte mail dans backend/.env."
        )
    ouvrir = ouvrir or _ouvrir_imap
    try:
        connexion = ouvrir(config)
    except (OSError, imaplib.IMAP4.error) as exc:
        raise ErreurLecture(
            "La boîte mail est injoignable. Vérifiez l’adresse, l’utilisateur "
            "et le mot de passe d’application."
        ) from exc
    try:
        statut, _ = connexion.login(config["utilisateur"], config["mot_de_passe"])
        if statut != "OK":
            raise ErreurLecture(
                "La boîte mail a refusé l’identifiant ou le mot de passe d’application."
            )
        statut, _ = connexion.select(config.get("dossier") or "INBOX", readonly=True)
        if statut != "OK":
            raise ErreurLecture("Le dossier de courrier est introuvable.")
        depuis = _date_imap(timezone.localdate() - timedelta(days=JOURS_RETRO))
        statut, data = connexion.search(None, "SINCE", depuis)
        if statut != "OK":
            raise ErreurLecture("La boîte mail n’a pas pu être parcourue.")
        numeros = (data[0] or b"").split()[-MESSAGES_MAX:]
        messages = []
        autorises = config.get("expediteurs") or []
        for numero in numeros:
            statut, entete_brut = connexion.fetch(
                numero,
                "(BODY.PEEK[HEADER.FIELDS (FROM MESSAGE-ID)])",
            )
            if statut != "OK":
                continue
            expediteur, _identifiant = _entete(_corps_fetch(entete_brut))
            if not expediteur_autorise(expediteur, autorises):
                continue
            statut, corps = connexion.fetch(numero, "(BODY.PEEK[])")
            if statut != "OK":
                continue
            brut = _corps_fetch(corps)
            if brut:
                messages.append(brut)
        return messages
    except ErreurLecture:
        raise
    except (OSError, imaplib.IMAP4.error) as exc:
        raise ErreurLecture(
            "La boîte mail est injoignable. Vérifiez l’adresse, l’utilisateur "
            "et le mot de passe d’application."
        ) from exc
    finally:
        try:
            connexion.logout()
        except Exception:
            pass


def _noter(resultat, texte):
    if texte and texte not in resultat["notes"] and len(resultat["notes"]) < 20:
        resultat["notes"].append(texte)


def _logements_annonces(analyse, texte):
    cible = normaliser(analyse.annonce)
    texte_norm = normaliser(texte)
    trouves = []
    for logement in Logement.objects.all():
        cle = normaliser(logement.annonce_airbnb)
        if len(cle) < 3:
            continue
        if (cible and (cle == cible or cle in cible or cible in cle)) or cle in texte_norm:
            trouves.append(logement)
    return trouves


def _par_code(code):
    if not code:
        return None
    return Reservation.objects.filter(code_airbnb=code, blocage=False).first()


def _par_dates(logement, analyse):
    if logement is None or not analyse.arrivee or not analyse.depart:
        return None
    candidats = list(
        Reservation.objects.filter(
            logement=logement,
            date_arrivee=analyse.arrivee,
            date_depart=analyse.depart,
            canal=Reservation.Canal.AIRBNB,
            blocage=False,
        )
    )
    actifs = [reservation for reservation in candidats if not reservation.annulee]
    if len(actifs) == 1:
        return actifs[0]
    if len(actifs) > 1:
        return actifs
    if len(candidats) == 1:
        return candidats[0]
    return None


def _trouver_reservation(analyse, logement):
    par_code = _par_code(analyse.code)
    if par_code is not None:
        return par_code, par_code.logement
    trouve = _par_dates(logement, analyse)
    if isinstance(trouve, list):
        return trouve, logement
    if trouve is not None:
        return trouve, logement
    return None, logement


def _appliquer_champs(reservation, analyse, changer_dates):
    if (
        analyse.voyageur
        and (reservation.client_nom in {"", NOM_CLIENT} or not reservation.client_nom)
    ):
        reservation.client_nom = analyse.voyageur
    if analyse.montant_fcfa and (
        reservation.montant_prevu == 0 or analyse.type == "modification"
    ):
        reservation.montant_prevu = analyse.montant_fcfa
    if analyse.nombre_voyageurs and (
        not reservation.nombre_voyageurs or analyse.type == "modification"
    ):
        reservation.nombre_voyageurs = analyse.nombre_voyageurs
    if analyse.code and not reservation.code_airbnb:
        reservation.code_airbnb = analyse.code
    if not reservation.client_telephone:
        reservation.client_telephone = TELEPHONE_A_COMPLETER
    if reservation.canal != Reservation.Canal.AIRBNB:
        reservation.canal = Reservation.Canal.AIRBNB
    if changer_dates and analyse.arrivee and analyse.depart:
        reservation.date_arrivee = analyse.arrivee
        reservation.date_depart = analyse.depart
    if reservation.annulee and analyse.type != "annulation":
        reservation.annulee = False
        reservation.annulee_le = None


def _sauver(reservation, echeances):
    with transaction.atomic():
        reservation.save()
        if echeances and reservation.montant_prevu and not reservation.blocage and not reservation.annulee:
            reservation.generer_echeances()


def _completer(reservation, analyse):
    avant_dates = (reservation.date_arrivee, reservation.date_depart)
    avant_montant = reservation.montant_prevu
    dates_differentes = bool(
        analyse.arrivee
        and analyse.depart
        and (analyse.arrivee != reservation.date_arrivee or analyse.depart != reservation.date_depart)
    )
    _appliquer_champs(reservation, analyse, dates_differentes)
    echeances = dates_differentes or reservation.montant_prevu != avant_montant
    try:
        _sauver(reservation, echeances)
        return dates_differentes, ""
    except (ValidationError, IntegrityError):
        reservation.refresh_from_db()
        _appliquer_champs(reservation, analyse, changer_dates=False)
        try:
            _sauver(reservation, reservation.montant_prevu != avant_montant)
        except (ValidationError, IntegrityError):
            reservation.refresh_from_db()
        return False, MESSAGE_LOGEMENT_OCCUPE


def _creer(logement, analyse):
    reservation = Reservation(
        logement=logement,
        client_nom=analyse.voyageur or NOM_CLIENT,
        client_telephone=TELEPHONE_A_COMPLETER,
        canal=Reservation.Canal.AIRBNB,
        mode=Reservation.Mode.NUITEE,
        date_arrivee=analyse.arrivee,
        date_depart=analyse.depart,
        montant_prevu=analyse.montant_fcfa or 0,
        code_airbnb=analyse.code,
        nombre_voyageurs=analyse.nombre_voyageurs,
    )
    _sauver(reservation, bool(reservation.montant_prevu))
    return reservation


def _nom_logement(logement, analyse):
    if logement is not None:
        return logement.nom
    return analyse.annonce or "Annonce Airbnb"


def _notes_champs(reservation, analyse, resultat):
    if not analyse.voyageur and reservation.client_nom in {"", NOM_CLIENT}:
        _noter(resultat, f"{reservation.logement.nom} : nom du voyageur à compléter.")
    if not analyse.nombre_voyageurs and not reservation.nombre_voyageurs:
        _noter(resultat, f"{reservation.logement.nom} : nombre de voyageurs à compléter.")
    if reservation.montant_prevu == 0:
        if analyse.devise_autre:
            _noter(
                resultat,
                f"{reservation.logement.nom} : montant {analyse.devise_autre}, à saisir en FCFA.",
            )
        else:
            _noter(resultat, f"{reservation.logement.nom} : montant à compléter.")
    if not analyse.code and not reservation.code_airbnb:
        _noter(resultat, f"{reservation.logement.nom} : code de confirmation à compléter.")


def appliquer_message(analyse, texte, resultat):
    if analyse.type == "inconnu":
        resultat["ignorees"] += 1
        return
    logements = _logements_annonces(analyse, texte)
    logement = logements[0] if len(logements) == 1 else None
    if len(logements) > 1 and not analyse.code:
        _noter(
            resultat,
            "Plusieurs logements correspondent à cet e-mail. "
            "Précisez le nom de l’annonce dans chaque fiche.",
        )
        resultat["ignorees"] += 1
        return
    reservation, logement_trouve = _trouver_reservation(analyse, logement)
    if isinstance(reservation, list):
        _noter(resultat, f"{logement.nom} : plusieurs séjours sur ces dates, e-mail ignoré.")
        resultat["ignorees"] += 1
        return
    if reservation is None and logement is None:
        nom = analyse.annonce or "sans nom d’annonce"
        _noter(
            resultat,
            f"Annonce non reconnue (« {nom} »). "
            "Indiquez ce nom dans la fiche du logement.",
        )
        resultat["ignorees"] += 1
        return
    logement = logement_trouve or logement

    if analyse.type == "annulation":
        if reservation is None:
            _noter(
                resultat,
                f"{_nom_logement(logement, analyse)} : annulation sans séjour correspondant"
                + (f" ({analyse.code})" if analyse.code else "")
                + ".",
            )
            resultat["ignorees"] += 1
            return
        if not reservation.annulee:
            reservation.annulee = True
            reservation.annulee_le = timezone.localdate()
            reservation.save()
            resultat["annulees"] += 1
            _noter(
                resultat,
                f"{reservation.logement.nom} : séjour de {reservation.client_nom} annulé. "
                "L’encaissement éventuel est conservé.",
            )
        return

    if reservation is None:
        if not analyse.arrivee or not analyse.depart or analyse.depart <= analyse.arrivee:
            _noter(
                resultat,
                f"{logement.nom} : dates illisibles, séjour non créé. À saisir à la main.",
            )
            resultat["ignorees"] += 1
            return
        try:
            reservation = _creer(logement, analyse)
        except (ValidationError, IntegrityError):
            _noter(resultat, f"{logement.nom} : {MESSAGE_LOGEMENT_OCCUPE}")
            resultat["ignorees"] += 1
            return
        resultat["creees"] += 1
        _noter(
            resultat,
            f"{logement.nom} : séjour créé pour {reservation.client_nom}, "
            f"du {reservation.date_arrivee.isoformat()} au {reservation.date_depart.isoformat()}.",
        )
        _notes_champs(reservation, analyse, resultat)
        return

    etait_annulee = reservation.annulee
    dates_changees, conflit = _completer(reservation, analyse)
    if conflit and not dates_changees:
        _noter(resultat, f"{reservation.logement.nom} : {conflit}")
    if dates_changees:
        resultat["modifiees"] += 1
        _noter(
            resultat,
            f"{reservation.logement.nom} : séjour de {reservation.client_nom} mis à jour, "
            f"du {reservation.date_arrivee.isoformat()} au {reservation.date_depart.isoformat()}.",
        )
    elif not etait_annulee:
        resultat["completees"] += 1
        _noter(
            resultat,
            f"{reservation.logement.nom} : séjour de {reservation.client_nom} complété"
            + (f" ({reservation.code_airbnb})" if reservation.code_airbnb else "")
            + ".",
        )
    else:
        resultat["modifiees"] += 1
        _noter(resultat, f"{reservation.logement.nom} : séjour de {reservation.client_nom} rétabli.")
    _notes_champs(reservation, analyse, resultat)


def _identifiant_message(analyse, brut):
    identifiant = (analyse.message_id or "").strip()
    if identifiant:
        return identifiant[:500]
    import hashlib

    return "sans-id:" + hashlib.sha256(brut if isinstance(brut, bytes) else brut.encode()).hexdigest()


def executer_lecture(messages=None):
    """Traite les messages fournis, ou ceux de la boîte si ``messages`` est omis.

    Aucun appel réseau n’est fait quand ``messages`` est une liste, même vide.
    """
    resultat = resultat_lecture_vide()
    if messages is None:
        if not imap_configure():
            resultat["erreur"] = (
                "La lecture des e-mails n’est pas configurée. "
                "Renseignez la boîte mail dans backend/.env."
            )
            resultat["resume"] = phrase_lecture(resultat)
            _memoriser(resultat)
            return resultat
        try:
            messages = lire_boite()
        except ErreurLecture as exc:
            resultat["erreur"] = str(exc)
            resultat["resume"] = phrase_lecture(resultat)
            _memoriser(resultat)
            return resultat

    nouveaux = 0
    for brut in messages:
        if isinstance(brut, str):
            brut = brut.encode("utf-8")
        analyse = analyser_email(brut)
        _sujet, _identifiant, texte = texte_du_message(brut)
        identifiant = _identifiant_message(analyse, brut)
        if MessageEmailTraite.objects.filter(message_id=identifiant).exists():
            continue
        nouveaux += 1
        try:
            appliquer_message(analyse, texte, resultat)
        except Exception:
            _noter(resultat, "Un e-mail n’a pas pu être lu. Les autres continuent.")
            resultat["ignorees"] += 1
        MessageEmailTraite.objects.get_or_create(message_id=identifiant)

    if nouveaux == 0 and not resultat["erreur"]:
        resultat["rien_de_nouveau"] = True
    resultat["resume"] = phrase_lecture(resultat)
    _memoriser(resultat)
    return resultat


def _memoriser(resultat):
    lecture = LectureEmails.objects.order_by("id").first()
    if lecture is None:
        LectureEmails.objects.create(le=timezone.now(), resultat=resultat)
        return
    lecture.le = timezone.now()
    lecture.resultat = resultat
    lecture.save(update_fields=["le", "resultat"])


def etat_lecture():
    lecture = LectureEmails.objects.order_by("id").first()
    if lecture is None:
        return None, {}
    return lecture.le, lecture.resultat or {}
