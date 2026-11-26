"""Lecture des textes d’e-mails Airbnb, sans base de données ni réseau.

Les fonctions de ce module sont pures : elles reçoivent le message et
renvoient les champs reconnus. Le format des e-mails Airbnb change parfois ;
un vrai message pourra demander un ajustement ici.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from email import policy
from email.parser import BytesParser
from html import unescape

MOIS = {
    "janvier": 1,
    "janv": 1,
    "jan": 1,
    "january": 1,
    "fevrier": 2,
    "février": 2,
    "fevr": 2,
    "févr": 2,
    "feb": 2,
    "february": 2,
    "mars": 3,
    "mar": 3,
    "march": 3,
    "avril": 4,
    "avr": 4,
    "apr": 4,
    "april": 4,
    "mai": 5,
    "may": 5,
    "juin": 6,
    "jun": 6,
    "june": 6,
    "juillet": 7,
    "juil": 7,
    "jul": 7,
    "july": 7,
    "aout": 8,
    "août": 8,
    "august": 8,
    "aug": 8,
    "septembre": 9,
    "sept": 9,
    "sep": 9,
    "september": 9,
    "octobre": 10,
    "oct": 10,
    "october": 10,
    "novembre": 11,
    "nov": 11,
    "november": 11,
    "decembre": 12,
    "décembre": 12,
    "dec": 12,
    "december": 12,
}

_CODE = re.compile(r"\b(HM[A-Z0-9]{6,10})\b", re.IGNORECASE)
_JOUR = r"(\d{1,2})(?:er)?"
_MOIS = r"([A-Za-zÀ-ÿ]{3,})"
_ANNEE = r"(\d{4})"
_DATE_JOUR_MOIS = re.compile(rf"{_JOUR}\s+{_MOIS}\s+{_ANNEE}", re.IGNORECASE)
_DATE_MOIS_JOUR = re.compile(rf"{_MOIS}\s+{_JOUR},?\s+{_ANNEE}", re.IGNORECASE)
_PLAGE_JOURS = re.compile(
    rf"{_JOUR}\s*[–—-]\s*{_JOUR}\s+{_MOIS}\s+{_ANNEE}",
    re.IGNORECASE,
)
_PLAGE_MOIS = re.compile(
    rf"{_MOIS}\s+{_JOUR}\s*[–—-]\s*{_JOUR},?\s+{_ANNEE}",
    re.IGNORECASE,
)
_MONTANT_FCFA = re.compile(
    r"(?:XOF|FCFA|F\s?CFA)\s*(\d{1,3}(?:[ \u00a0\u202f.,]\d{3})+|\d+)"
    r"|(\d{1,3}(?:[ \u00a0\u202f.,]\d{3})+|\d+)\s*(?:XOF|FCFA|F\s?CFA)",
    re.IGNORECASE,
)
_MONTANT_AUTRE = re.compile(
    r"(?:(EUR|USD|GBP|€|\$|£)\s*(\d+(?:[.,]\d{2})?)|(\d+(?:[.,]\d{2})?)\s*(EUR|USD|GBP|€|\$|£))",
    re.IGNORECASE,
)
_NOMS_REFUSES = ("airbnb", "reservation", "réservation", "confirmed", "confirmée")


@dataclass(frozen=True)
class MessageAnalyse:
    type: str
    code: str = ""
    voyageur: str = ""
    nombre_voyageurs: int | None = None
    arrivee: date | None = None
    depart: date | None = None
    annonce: str = ""
    montant_fcfa: int | None = None
    devise_autre: str = ""
    sujet: str = ""
    message_id: str = ""


def normaliser(texte):
    brut = unicodedata.normalize("NFKD", texte or "")
    sans_accents = "".join(caractere for caractere in brut if not unicodedata.combining(caractere))
    return re.sub(r"\s+", " ", sans_accents).casefold().strip()


def _sans_html(texte):
    sans_blocs = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", texte or "")
    avec_sauts = re.sub(r"(?i)<br\s*/?>", "\n", sans_blocs)
    avec_sauts = re.sub(r"(?i)</p>", "\n", avec_sauts)
    sans_balises = re.sub(r"(?s)<[^>]+>", " ", avec_sauts)
    return unescape(sans_balises)


def texte_du_message(brut):
    """Retourne le sujet, l’identifiant et le texte lisible. Ne conserve rien."""
    if isinstance(brut, str):
        brut = brut.encode("utf-8")
    message = BytesParser(policy=policy.default).parsebytes(brut)
    sujet = str(message.get("subject") or "")
    identifiant = str(message.get("message-id") or "").strip()
    parties = []
    if message.is_multipart():
        for partie in message.walk():
            if partie.get_content_disposition() == "attachment":
                continue
            if partie.get_content_type() == "text/plain":
                parties.append(partie.get_content())
        if not parties:
            for partie in message.walk():
                if partie.get_content_type() == "text/html":
                    parties.append(_sans_html(partie.get_content()))
    else:
        contenu = message.get_content()
        if message.get_content_type() == "text/html":
            contenu = _sans_html(contenu)
        parties.append(contenu)
    return sujet, identifiant, "\n".join(parties)


def _type_message(sujet, texte):
    ensemble = normaliser(f"{sujet}\n{texte[:1500]}")
    if any(mot in ensemble for mot in ("annulee", "annule", "canceled", "cancelled")):
        return "annulation"
    if any(
        mot in ensemble
        for mot in ("modifiee", "modification", "updated", "has been changed", "changes to")
    ):
        return "modification"
    if any(mot in ensemble for mot in ("confirmee", "confirmed")):
        return "confirmation"
    return "inconnu"


def _mois(nom):
    return MOIS.get(normaliser(nom).replace(".", ""))


def _date(jour, mois, annee):
    try:
        return date(int(annee), mois, int(jour))
    except (TypeError, ValueError):
        return None


def _dates_dans(texte):
    trouvees = []
    for expression in (_DATE_JOUR_MOIS, _DATE_MOIS_JOUR):
        for trouve in expression.finditer(texte or ""):
            if expression is _DATE_JOUR_MOIS:
                jour, mois_nom, annee = trouve.groups()
            else:
                mois_nom, jour, annee = trouve.groups()
            journee = _date(jour, _mois(mois_nom), annee)
            if journee and journee not in trouvees:
                trouvees.append(journee)
    trouvees.sort()
    return trouvees


def _plage(texte):
    trouve = _PLAGE_JOURS.search(texte or "")
    if trouve:
        debut, fin, mois_nom, annee = trouve.groups()
        mois = _mois(mois_nom)
        return _date(debut, mois, annee), _date(fin, mois, annee)
    trouve = _PLAGE_MOIS.search(texte or "")
    if trouve:
        mois_nom, debut, fin, annee = trouve.groups()
        mois = _mois(mois_nom)
        return _date(debut, mois, annee), _date(fin, mois, annee)
    return None, None


def _date_apres(texte, etiquette):
    morceau = re.search(
        rf"(?is){etiquette}.{{0,80}}?({_JOUR}\s+{_MOIS}\s+{_ANNEE}|{_MOIS}\s+{_JOUR},?\s+{_ANNEE})",
        texte or "",
    )
    if not morceau:
        return None
    trouvees = _dates_dans(morceau.group(1))
    return trouvees[0] if trouvees else None


def dates_sejour(texte):
    debut, fin = _plage(texte)
    if debut and fin and fin > debut:
        return debut, fin
    arrivee = _date_apres(texte, r"(?:arrivée|arrivee|check-?in)")
    depart = _date_apres(texte, r"(?:départ|depart|check-?out)")
    if arrivee and depart and depart > arrivee:
        return arrivee, depart
    trouvees = _dates_dans(texte)
    if len(trouvees) >= 2 and trouvees[1] > trouvees[0]:
        return trouvees[0], trouvees[1]
    return None, None


def _ligne_apres(texte, etiquette):
    trouve = re.search(rf"(?im)^[ \t]*{etiquette}[ \t]*[:：]?[ \t]*(.*)$", texte or "")
    if not trouve:
        return ""
    valeur = trouve.group(1).strip()
    if valeur:
        return valeur.splitlines()[0].strip()
    suite = re.search(
        rf"(?im)^[ \t]*{etiquette}[ \t]*[:：]?[ \t]*\n+[ \t]*(\S[^\n]*)$",
        texte or "",
    )
    return suite.group(1).strip() if suite else ""


def _nom_valide(nom):
    nom = re.sub(r"\s+", " ", (nom or "")).strip(" -–—:.")
    if not nom or len(nom) > 120 or len(nom) < 2 or re.match(r"\d", nom):
        return ""
    compare = normaliser(nom)
    if any(refuse in compare for refuse in _NOMS_REFUSES):
        return ""
    if not re.search(r"[a-zà-ÿ]", compare):
        return ""
    return nom


def voyageur(sujet, texte):
    for etiquette in (
        r"nom du voyageur",
        r"voyageur(?!s)",
        r"guest name",
        r"guest(?!s)",
    ):
        nom = _nom_valide(_ligne_apres(texte, etiquette))
        if nom:
            return nom
    for source in (texte, sujet):
        trouve = re.search(
            r"(?im)^[ \t]*([A-ZÀ-Ÿ][\w'’-]+(?:[ \t]+[A-ZÀ-Ÿ][\w'’-]+){0,3})"
            r"[ \t]+arrive(?:s|nt)?\b",
            source or "",
        )
        nom = _nom_valide(trouve.group(1) if trouve else "")
        if nom:
            return nom
    return ""


def nombre_voyageurs(texte):
    texte = texte or ""
    total = re.search(r"(?i)(\d{1,2})[ \t]+(?:voyageurs?|guests?)\b", texte)
    if total:
        return int(total.group(1))
    compte = 0
    trouve = False
    for expression in (
        r"(\d{1,2})[ \t]+(?:adultes?|adults?)\b",
        r"(\d{1,2})[ \t]+(?:enfants?|children|child)\b",
        r"(\d{1,2})[ \t]+(?:bébés?|bebes?|infants?)\b",
    ):
        morceau = re.search(expression, texte, re.IGNORECASE)
        if morceau:
            compte += int(morceau.group(1))
            trouve = True
    return compte if trouve and compte > 0 else None


def _entier(morceau):
    chiffres = re.sub(r"[^\d]", "", morceau or "")
    if not chiffres:
        return None
    return int(chiffres)


def montant_fcfa(texte):
    """Versement indiqué en FCFA ou en XOF. Une autre devise n’est pas convertie."""
    texte = texte or ""
    zone = texte
    ancre = re.search(
        r"(?is)(vous gagnerez|you earn|versement|payout|total payout).{0,80}",
        texte,
    )
    if ancre:
        zone = ancre.group(0)
    trouve = _MONTANT_FCFA.search(zone) or _MONTANT_FCFA.search(texte)
    if trouve:
        return _entier(trouve.group(1) or trouve.group(2)), ""
    autre = _MONTANT_AUTRE.search(zone) or _MONTANT_AUTRE.search(texte)
    if not autre:
        return None, ""
    devise = (autre.group(1) or autre.group(4) or "").upper().replace("€", "EUR").replace("$", "USD").replace("£", "GBP")
    valeur = (autre.group(2) or autre.group(3) or "").replace(".", ",")
    return None, f"{valeur} {devise}".strip()


def annonce(texte):
    for etiquette in (r"annonce", r"listing", r"logement"):
        valeur = _ligne_apres(texte, etiquette)
        if valeur and len(valeur) <= 160:
            return valeur.strip()
    return ""


def code_confirmation(texte):
    return extraire_premier_code(texte)


def extraire_premier_code(texte):
    trouve = _CODE.search(texte or "")
    return trouve.group(1).upper() if trouve else ""


def analyser_email(brut):
    sujet, identifiant, texte = texte_du_message(brut)
    type_message = _type_message(sujet, texte)
    arrivee, depart = dates_sejour(f"{sujet}\n{texte}")
    montant, devise = montant_fcfa(texte)
    return MessageAnalyse(
        type=type_message,
        code=extraire_premier_code(f"{sujet}\n{texte}"),
        voyageur=voyageur(sujet, texte),
        nombre_voyageurs=nombre_voyageurs(texte),
        arrivee=arrivee,
        depart=depart,
        annonce=annonce(texte),
        montant_fcfa=montant,
        devise_autre=devise,
        sujet=sujet,
        message_id=identifiant,
    )
