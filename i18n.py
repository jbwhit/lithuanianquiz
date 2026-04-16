"""Shared UI language helpers."""

from typing import Any

UI_LANGUAGE_KEY = "ui_lang"
SUPPORTED_UI_LANGS = {"en", "lt"}

_LT_FIXUPS: tuple[tuple[str, str], ...] = (
    ("Lietuvisku", "Lietuviškų"),
    ("Lietuvisko", "Lietuviško"),
    ("Lietuviski", "Lietuviški"),
    ("Lietuviu", "Lietuvių"),
    ("lietuviskai", "lietuviškai"),
    ("lietuviska", "lietuviška"),
    ("lietuviskas", "lietuviškas"),
    ("lietuviski", "lietuviški"),
    ("Lietuvis", "Lietuviš"),
    ("Atsaukti", "Atšaukti"),
    ("Ivyko Klaida", "Įvyko klaida"),
    ("Ivyko", "Įvyko"),
    ("Pradzia", "Pradžia"),
    ("Atgal i ", "Atgal į "),
    ("Jusu", "Jūsų"),
    ("jusu", "jūsų"),
    ("isvalyta", "išvalyta"),
    ("Irasykite", "Įrašykite"),
    ("Atpazinimas", "Atpažinimas"),
    ("atpazinimas", "atpažinimas"),
    ("atpazinkite", "atpažinkite"),
    ("atpazink", "atpažink"),
    ("Skaiciu", "Skaičių"),
    ("skaiciu", "skaičių"),
    ("Skaiciai", "Skaičiai"),
    ("skaiciai", "skaičiai"),
    ("Skaiciaus", "Skaičiaus"),
    ("skaiciaus", "skaičiaus"),
    ("Skaiciumi", "Skaičiumi"),
    ("skaiciumi", "skaičiumi"),
    ("Skaicius", "Skaičius"),
    ("skaicius", "skaičius"),
    ("Amziaus", "Amžiaus"),
    ("amziaus", "amžiaus"),
    ("Amzius", "Amžius"),
    ("amzius", "amžius"),
    ("amziu", "amžių"),
    ("frazes", "frazės"),
    ("Fraze", "Frazė"),
    ("kainu", "kainų"),
    ("Kainu", "Kainų"),
    ("israiskas", "išraiškas"),
    ("pilna", "pilną"),
    ("atsakyma lietuviskai", "atsakymą lietuviškai"),
    ("atsakyma lietuviškai", "atsakymą lietuviškai"),
    ("atsakyma su", "atsakymą su"),
    ("Atsitiktines", "Atsitiktinės"),
    ("visu", "visų"),
    ("demesio", "dėmesio"),
    ("Perziurekite", "Peržiūrėkite"),
    ("Ziureti", "Žiūrėti"),
    ("viska", "viską"),
    ("Is Viso", "Iš viso"),
    ("Istorijos dar nera", "Istorijos dar nėra"),
    ("Cia", "Čia"),
    ("Dabartine", "Dabartinė"),
    ("Uzduotis", "Užduotis"),
    ("Uzduotys", "Užduotys"),
    ("uzduociu", "užduočių"),
    ("Uzduociu", "Užduočių"),
    ("puse", "pusė"),
    ("ketvircio", "ketvirčio"),
    ("sudet", "sudėt"),
    ("temperaturos", "temperatūros"),
    ("pasakyma", "pasakymą"),
    ("Pazanga", "Pažanga"),
    ("pazanga", "pažanga"),
    ("Mokykites", "Mokykitės"),
    ("metu", "metų"),
    ("ivardz", "įvardž"),
    ("zodzi", "žodži"),
    ("Kurimas", "Kūrimas"),
    ("desimt", "dešimt"),
    ("pagrindiniu", "pagrindinių"),
    ("kalbej", "kalbėj"),
    ("kalbet", "kalbėt"),
    ("privaciam", "privačiam"),
    ("testu duomenis", "testų duomenis"),
    ("minuciu", "minučių"),
    ("apie laika", "apie laiką"),
    ("apie ora", "apie orą"),
    ("apie temperatura ", "apie temperatūrą "),
    ("reguliaria praktika!", "reguliarią praktiką!"),
    ("tinkama ivardi ir linksni", "tinkamą įvardį ir linksnį"),
)


def normalize_ui_lang(value: Any) -> str:
    """Return a supported UI language code or default to English."""
    return value if value in SUPPORTED_UI_LANGS else "en"


def ui_lang_from_session(session: dict[str, Any]) -> str:
    """Read and normalize UI language from session state."""
    return normalize_ui_lang(session.get(UI_LANGUAGE_KEY))


def tr(lang: str, english: str, lithuanian: str) -> str:
    """Translate between English and Lithuanian UI strings."""
    if normalize_ui_lang(lang) != "lt":
        return english

    text = lithuanian
    for src, dst in _LT_FIXUPS:
        text = text.replace(src, dst)
    return text
