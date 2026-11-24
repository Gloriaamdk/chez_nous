import calendar
from datetime import date


def mois_suivant(jour):
    mois = jour.month + 1
    annee = jour.year
    if mois == 13:
        mois = 1
        annee += 1
    dernier_jour = calendar.monthrange(annee, mois)[1]
    return date(annee, mois, min(jour.day, dernier_jour))


def dates_echeances(mode, arrivee, depart):
    if mode == "nuitee":
        return [arrivee]
    dates = []
    jour = arrivee
    while jour < depart:
        dates.append(jour)
        suivant = mois_suivant(jour)
        if suivant <= jour:
            break
        jour = suivant
    return dates
