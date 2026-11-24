import unicodedata

from babel import Locale

# Codes CLDR qui ne sont pas des pays ISO.
_EXCLUS = {"EU", "EZ", "UN", "XA", "XB", "ZZ", "QO", "QU"}


def _cle_francaise(nom):
    decompose = unicodedata.normalize("NFD", nom)
    sans_accents = "".join(
        caractere
        for caractere in decompose
        if unicodedata.category(caractere) != "Mn"
    )
    return sans_accents.casefold()


def pays_francais():
    """Retourne les pays ISO avec leur libellé français, triés par libellé."""
    territoires = Locale.parse("fr").territories
    pays = [
        (code, nom)
        for code, nom in territoires.items()
        if len(code) == 2 and code.isalpha() and code not in _EXCLUS
    ]
    return tuple(sorted(pays, key=lambda item: _cle_francaise(item[1])))


PAYS_PAR_CODE = dict(pays_francais())
