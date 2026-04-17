"""UI component functions for Lithuanian price quiz."""

from typing import Any
from urllib.parse import quote

from fasthtml.common import *
from i18n import tr
from monsterui.all import *
from quiz import highlight_diff
from time_engine import ORDINALS_GEN, ORDINALS_NOM, _next_hour

# ------------------------------------------------------------------
# Page shell
# ------------------------------------------------------------------


MODULE_NAMES = {
    "numbers-20",
    "numbers-99",
    "age",
    "weather",
    "prices",
    "time",
    "practice-all",
}


def _is_lt(lang: str) -> bool:
    return lang == "lt"


def _txt(lang: str, english: str, lithuanian: str) -> str:
    return tr(lang, english, lithuanian)


def page_shell(
    *content: Any,
    user_name: str | None = None,
    active_module: str | None = None,
    lang: str = "en",
    diacritic_tolerant: bool = False,
    current_path: str = "/",
) -> Div:
    """Full page wrapper with navbar."""
    brand = A(
        DivLAligned(
            Span("🇱🇹", cls="text-2xl mr-2"),
            H3(
                _txt(lang, "Lithuanian", "Lietuviskai"),
                cls=(TextT.xl, TextT.bold, "text-primary"),
            ),
            P(_txt(lang, "Practice", "Praktika"), cls=TextT.muted),
            cls="items-center",
        ),
        href="/",
        cls="no-underline",
    )
    # Modules dropdown
    is_module_active = active_module in MODULE_NAMES
    modules_btn = A(
        _txt(lang, "Modules", "Moduliai"),
        UkIcon("chevron-down", cls="ml-1", height=14, width=14),
        cls="uk-btn uk-btn-ghost"
        + (" uk-active font-bold" if is_module_active else ""),
    )
    modules_dropdown = DropDownNavContainer(
        Li(A(_txt(lang, "Numbers 1-20", "Skaiciai 1-20"), href="/numbers-20")),
        Li(A(_txt(lang, "Numbers 1-99", "Skaiciai 1-99"), href="/numbers-99")),
        Li(A(_txt(lang, "Age", "Amzius"), href="/age")),
        Li(A(_txt(lang, "Weather", "Oras"), href="/weather")),
        Li(A(_txt(lang, "Prices", "Kainos"), href="/prices")),
        Li(A(_txt(lang, "Time", "Laikas"), href="/time")),
        NavDividerLi(),
        Li(A(_txt(lang, "Practice All", "Bendra Praktika"), href="/practice-all")),
        Li(A(_txt(lang, "About", "Apie"), href="/about")),
    )
    modules_nav = Div(modules_btn, modules_dropdown, cls="inline-block")
    language_toggle = Div(
        A(
            "English",
            href="/set-language?lang=en",
            cls="uk-btn uk-btn-ghost"
            + (" uk-active font-bold" if lang == "en" else ""),
        ),
        Span("|", cls="text-base-content/50"),
        A(
            "Lietuviskai",
            href="/set-language?lang=lt",
            cls="uk-btn uk-btn-ghost"
            + (" uk-active font-bold" if lang == "lt" else ""),
        ),
        cls="inline-flex items-center gap-1",
    )
    strict_cls = "uk-btn uk-btn-ghost btn-sm"
    tolerant_cls = "uk-btn uk-btn-ghost btn-sm"
    if diacritic_tolerant:
        tolerant_cls += " uk-active font-bold"
    else:
        strict_cls += " uk-active font-bold"
    next_path = quote(current_path or "/", safe="/")
    mode_toggle = Div(
        Span(
            _txt(lang, "Input:", "Ivestis:"),
            cls=(TextT.sm, "text-base-content/60 mr-1"),
        ),
        A(
            _txt(lang, "Strict", "Grieztas"),
            href=f"/set-diacritic-mode?enabled=0&next_path={next_path}",
            cls=strict_cls,
        ),
        A(
            _txt(lang, "Tolerant", "Lankstus"),
            href=f"/set-diacritic-mode?enabled=1&next_path={next_path}",
            cls=tolerant_cls,
        ),
        cls="inline-flex items-center gap-1",
    )
    nav_items: list[Any] = [
        modules_nav,
        A(_txt(lang, "Stats", "Statistika"), href="/stats", cls="uk-btn uk-btn-ghost"),
        mode_toggle,
        A(
            _txt(lang, "Feedback", "Atsiliepimai"),
            href="https://github.com/jbwhit/lithuanianquiz/issues/new",
            cls="uk-btn uk-btn-ghost",
            target="_blank",
        ),
        language_toggle,
    ]
    if user_name:
        nav_items.extend(
            [
                Span(user_name, cls=(TextT.sm, "px-3 py-2")),
                A(
                    _txt(lang, "Logout", "Atsijungti"),
                    href="/logout",
                    cls="uk-btn uk-btn-ghost",
                ),
            ]
        )
    else:
        nav_items.append(
            A(
                _txt(lang, "Login", "Prisijungti"),
                href="/login",
                cls="uk-btn uk-btn-ghost",
            )
        )
    nav = Container(
        NavBar(
            *nav_items,
            brand=brand,
            sticky=True,
            cls="py-2",
        ),
        cls="max-w-6xl mx-auto",
    )
    return Div(nav, *content, cls="min-h-screen px-4")


def login_page_content(login_url: str, lang: str = "en") -> Container:
    """Centered login card."""
    return Container(
        DivCentered(
            Card(
                CardHeader(
                    DivCentered(
                        Span("🇱🇹", cls="text-5xl mb-3"),
                        H2(
                            _txt(
                                lang,
                                "Lithuanian Price Quiz",
                                "Kainos lietuviskai - testas",
                            ),
                            cls=(TextT.xl, TextT.bold),
                        ),
                        P(
                            _txt(
                                lang,
                                "Practice expressing prices in Lithuanian",
                                "Kainos lietuviskai - praktika",
                            ),
                            cls=TextPresets.muted_lg,
                        ),
                    )
                ),
                CardBody(
                    DivCentered(
                        A(
                            UkIcon("log-in", cls="mr-2"),
                            _txt(lang, "Login with Google", "Prisijungti su Google"),
                            href=login_url,
                            cls=(ButtonT.primary, "px-8 py-3 text-lg"),
                        ),
                        P(
                            _txt(
                                lang,
                                "Free and private. We only store your quiz progress, nothing else.",
                                "Nemokama ir privatu. Saugome tik testu duomenis jusu privaciam naudojimui.",
                            ),
                            cls="text-base-content/50 text-xs mt-4 max-w-xs text-center",
                        ),
                    )
                ),
                cls="shadow-xl border-t-4 border-t-primary w-full max-w-md",
            ),
            cls="min-h-[60vh]",
        ),
        cls=(ContainerT.xl, "px-8 py-16"),
    )


def landing_page_content(lang: str = "en") -> Container:
    """Landing page with module cards."""

    def _module_card(
        emoji: str,
        title: str,
        description: str,
        href: str,
        border_color: str,
        badge: str | None = None,
    ) -> Card:
        header_items: list[Any] = [
            Span(emoji, cls="text-4xl mb-2"),
            H3(title, cls=(TextT.lg, TextT.bold)),
        ]
        if badge:
            header_items.append(
                Span(
                    badge,
                    cls="text-xs font-bold text-success-content bg-success px-2 py-0.5 rounded-full",
                ),
            )
        return CardContainer(
            CardHeader(DivCentered(*header_items)),
            CardBody(
                P(description, cls="text-center text-base-content/70"),
                cls="flex-grow",
            ),
            CardFooter(
                DivCentered(
                    A(
                        _txt(lang, "Start Practicing", "Pradeti Praktika"),
                        href=href,
                        cls=(ButtonT.primary, "px-6 py-2"),
                    ),
                ),
                cls="mt-auto",
            ),
            cls=f"shadow-lg border-t-4 {border_color} h-full flex flex-col module-card",
        )

    return Container(
        DivCentered(
            Span("🇱🇹", cls="text-6xl mb-4"),
            H1(
                _txt(lang, "Lithuanian Practice", "Lietuviu kalbos praktika"),
                cls=(TextT.xl, TextT.bold),
            ),
            P(
                _txt(
                    lang,
                    "Master Lithuanian through adaptive exercises",
                    "Mokykites kalbeti lietuviskai per adaptyvias uzduotis",
                ),
                cls=TextPresets.muted_lg,
            ),
            cls="mb-10",
        ),
        Grid(
            _module_card(
                "🔢",
                _txt(lang, "Numbers 1-20", "Skaiciai 1-20"),
                _txt(
                    lang,
                    "Learn the basic Lithuanian number words.",
                    "Mokykites kalbeti apie skaicius.",
                ),
                "/numbers-20",
                "border-t-success",
                badge=_txt(lang, "Start here", "Pradekite cia"),
            ),
            _module_card(
                "🔢",
                _txt(lang, "Numbers 1-99", "Skaiciai 1-99"),
                _txt(
                    lang,
                    "All numbers including decades and compounds.",
                    "Visi skaiciai, iskaitant desimtis ir sudetinius.",
                ),
                "/numbers-99",
                "border-t-info",
            ),
            _module_card(
                "🎂",
                _txt(lang, "Age", "Amzius"),
                _txt(
                    lang,
                    "Practice expressing ages with dative pronouns (Man, Tau, Jam, Jai).",
                    "Mokykites kalbeti apie amziu parinkdami tinkama ivardi ir linksni.",
                ),
                "/age",
                "border-t-warning",
            ),
            _module_card(
                "🌡️",
                _txt(lang, "Weather", "Oras"),
                _txt(
                    lang,
                    "Practice expressing temperatures with laipsnis/laipsniai/laipsniu.",
                    "Praktikuokite temperaturos israiskas su laipsnis/laipsniai/laipsniu.",
                ),
                "/weather",
                "border-t-error",
            ),
            _module_card(
                "💶",
                _txt(lang, "Prices", "Kainos"),
                _txt(
                    lang,
                    "Practice expressing prices with Kokia kaina? (nominative) and Kiek kainuoja? (accusative).",
                    "Praktikuokite kainas su Kokia kaina? (vardininkas) ir Kiek kainuoja? (galininkas).",
                ),
                "/prices",
                "border-t-primary",
            ),
            _module_card(
                "🕐",
                _txt(lang, "Time", "Laikas"),
                _txt(
                    lang,
                    "Practice telling time: whole hours, half past, quarter past, and quarter to.",
                    "Mokykites kalbeti apie laika: pilnos valandos, puse, penkiolika minuciu po ir be penkiolikos minuciu.",
                ),
                "/time",
                "border-t-secondary",
            ),
            cols_md=2,
            cols_sm=1,
            gap=6,
        ),
        Div(
            _module_card(
                "🎯",
                _txt(lang, "Practice All", "Bendra Praktika"),
                _txt(
                    lang,
                    "Random exercises from all modules, weighted toward your weakest areas.",
                    "Atsitiktines uzduotys is visu moduliu, daugiau demesio silpniausioms vietoms.",
                ),
                "/practice-all",
                "border-t-accent",
            ),
            cls="mt-6 max-w-sm mx-auto",
        ),
        Div(
            P(
                UkIcon("shield", cls="inline mr-1", height=14, width=14),
                _txt(
                    lang,
                    "Free to use. No tracking beyond your current browser session. ",
                    "Nemokama. Sekimas nevykdomas uz dabartines narsykles sesijos ribu. ",
                ),
                A(_txt(lang, "Log in", "Prisijunkite"), href="/login", cls="underline"),
                _txt(
                    lang,
                    " only to save progress across visits.",
                    " tik jei norite issaugoti pazanga tarp apsilankymu.",
                ),
                cls="text-base-content/50 text-xs",
            ),
            cls="mt-10 text-center",
        ),
        cls=(ContainerT.xl, "px-8 py-16"),
    )


# ------------------------------------------------------------------
# Examples (collapsible)
# ------------------------------------------------------------------


def examples_section(lang: str = "en") -> Details:
    """Collapsible 'Show an example' section."""

    def _example(question: str, answer: str, case: str) -> Div:
        return Div(
            P(question, cls="font-medium text-base-content/80"),
            P(
                "→ ",
                Span(answer, cls="font-bold text-primary"),
                cls="mt-1",
            ),
            P(case, cls="text-xs text-base-content/50 mt-1 italic"),
            cls="p-3 bg-base-200 rounded-lg",
        )

    return Details(
        Summary(
            UkIcon("help-circle", cls="inline mr-1", height=16, width=16),
            _txt(lang, "Show an example", "Rodyti pavyzdi"),
            cls="cursor-pointer text-sm text-base-content/60 hover:text-base-content "
            "list-none mb-3 select-none",
        ),
        Div(
            _example(
                "Kokia kaina? (€5)",
                "penki eurai.",
                _txt(
                    lang,
                    "Nominative — stating the price directly",
                    "Vardininkas - tiesiogiai nurodoma kaina",
                ),
            ),
            _example(
                "Kiek kainuoja knyga? (€21)",
                "dvidešimt vieną eurą.",
                _txt(
                    lang,
                    "Accusative — saying what something costs",
                    "Galininkas - sakoma, kiek kas kainuoja",
                ),
            ),
            cls="grid grid-cols-1 gap-3 sm:grid-cols-2 mb-4",
        ),
    )


def time_examples_section(lang: str = "en") -> Details:
    """Collapsible examples for time exercises."""

    def _example(question: str, answer: str, note: str) -> Div:
        return Div(
            P(question, cls="font-medium text-base-content/80"),
            P(
                "→ ",
                Span(answer, cls="font-bold text-primary"),
                cls="mt-1",
            ),
            P(note, cls="text-xs text-base-content/50 mt-1 italic"),
            cls="p-3 bg-base-200 rounded-lg",
        )

    return Details(
        Summary(
            UkIcon("help-circle", cls="inline mr-1", height=16, width=16),
            _txt(lang, "Show an example", "Rodyti pavyzdi"),
            cls="cursor-pointer text-sm text-base-content/60 hover:text-base-content "
            "list-none mb-3 select-none",
        ),
        Div(
            _example(
                "Kiek valandų? (3:00)",
                "Trečia valanda.",
                _txt(
                    lang,
                    "Whole hour - feminine ordinal + valanda",
                    "Pilna valanda - moteriskos g. kelintinis + valanda",
                ),
            ),
            _example(
                "Kiek valandų? (2:30)",
                "Pusė trečios.",
                _txt(
                    lang,
                    "Half past - puse + genitive of next hour",
                    "Puse - puse + kitos valandos kilmininkas",
                ),
            ),
            _example(
                "Kiek valandų? (1:15)",
                "Ketvirtis antros.",
                _txt(
                    lang,
                    "Quarter past - ketvirtis + genitive of next hour",
                    "Ketvirtis po - ketvirtis + kitos valandos kilmininkas",
                ),
            ),
            _example(
                "Kiek valandų? (2:45)",
                "Be ketvirčio trečia.",
                _txt(
                    lang,
                    "Quarter to - be ketvircio + nominative of next hour",
                    "Be ketvircio - be ketvircio + kitos valandos vardininkas",
                ),
            ),
            cls="grid grid-cols-1 gap-3 sm:grid-cols-2 mb-4",
        ),
    )


def number_examples_section(max_number: int, lang: str = "en") -> Details:
    """Collapsible examples for number exercises."""

    def _example(question: str, answer: str, note: str) -> Div:
        return Div(
            P(question, cls="font-medium text-base-content/80"),
            P(
                "→ ",
                Span(answer, cls="font-bold text-primary"),
                cls="mt-1",
            ),
            P(note, cls="text-xs text-base-content/50 mt-1 italic"),
            cls="p-3 bg-base-200 rounded-lg",
        )

    if max_number <= 20:
        examples = Div(
            _example(
                _txt(lang, "How do you say 5?", "Kaip pasakyti 5?"),
                "penki",
                _txt(
                    lang,
                    "Produce - type the Lithuanian number word",
                    "Kurimas - irasykite lietuviska skaiciaus zodi",
                ),
            ),
            _example(
                _txt(
                    lang, "What number is penkiolika?", "Koks skaicius yra penkiolika?"
                ),
                "15",
                _txt(
                    lang,
                    "Recognize - identify the number from Lithuanian",
                    "Atpazinimas - nustatykite skaiciu is lietuvisko zodzio",
                ),
            ),
            cls="grid grid-cols-1 gap-3 sm:grid-cols-2 mb-4",
        )
    else:
        examples = Div(
            _example(
                _txt(lang, "How do you say 45?", "Kaip pasakyti 45?"),
                "keturiasdešimt penki",
                _txt(
                    lang,
                    "Produce - compounds have two words",
                    "Kurimas - sudetiniai skaiciai turi du zodzius",
                ),
            ),
            _example(
                _txt(
                    lang, "What number is trisdesimt?", "Koks skaicius yra trisdesimt?"
                ),
                "30",
                _txt(
                    lang,
                    "Recognize - identify the number from Lithuanian",
                    "Atpazinimas - nustatykite skaiciu is lietuvisko zodzio",
                ),
            ),
            cls="grid grid-cols-1 gap-3 sm:grid-cols-2 mb-4",
        )

    return Details(
        Summary(
            UkIcon("help-circle", cls="inline mr-1", height=16, width=16),
            _txt(lang, "Show an example", "Rodyti pavyzdi"),
            cls="cursor-pointer text-sm text-base-content/60 hover:text-base-content "
            "list-none mb-3 select-none",
        ),
        examples,
    )


def age_examples_section(lang: str = "en") -> Details:
    """Collapsible examples for age exercises."""

    def _example(question: str, answer: str, note: str) -> Div:
        return Div(
            P(question, cls="font-medium text-base-content/80"),
            P(
                "→ ",
                Span(answer, cls="font-bold text-primary"),
                cls="mt-1",
            ),
            P(note, cls="text-xs text-base-content/50 mt-1 italic"),
            cls="p-3 bg-base-200 rounded-lg",
        )

    return Details(
        Summary(
            UkIcon("help-circle", cls="inline mr-1", height=16, width=16),
            _txt(lang, "Show an example", "Rodyti pavyzdi"),
            cls="cursor-pointer text-sm text-base-content/60 hover:text-base-content "
            "list-none mb-3 select-none",
        ),
        Div(
            _example(
                _txt(lang, "He is 25 years old.", "Jam yra 25 metai."),
                "Jam dvidešimt penkeri metai.",
                _txt(
                    lang,
                    "Produce - dative pronoun + number word + metai/metu",
                    "Kurimas - naudininko ivardis + skaiciaus zodis + metai/metu",
                ),
            ),
            _example(
                "Jai penkiolika metų.",
                "15",
                _txt(
                    lang,
                    "Recognize - identify the age from Lithuanian",
                    "Atpazinimas - nustatykite amziu is lietuviskos frazes",
                ),
            ),
            cls="grid grid-cols-1 gap-3 sm:grid-cols-2 mb-4",
        ),
    )


def weather_examples_section(lang: str = "en") -> Details:
    """Collapsible examples for weather exercises."""

    def _example(question: str, answer: str, note: str) -> Div:
        return Div(
            P(question, cls="font-medium text-base-content/80"),
            P(
                "→ ",
                Span(answer, cls="font-bold text-primary"),
                cls="mt-1",
            ),
            P(note, cls="text-xs text-base-content/50 mt-1 italic"),
            cls="p-3 bg-base-200 rounded-lg",
        )

    return Details(
        Summary(
            UkIcon("help-circle", cls="inline mr-1", height=16, width=16),
            _txt(lang, "Show an example", "Rodyti pavyzdi"),
            cls="cursor-pointer text-sm text-base-content/60 hover:text-base-content "
            "list-none mb-3 select-none",
        ),
        Div(
            _example(
                _txt(lang, "How do you say 25C?", "Kaip pasakyti 25C?"),
                "dvidešimt penki laipsniai",
                _txt(
                    lang,
                    "Produce - number word + correct degree form",
                    "Kurimas - skaiciaus zodis + tinkama laipsnio forma",
                ),
            ),
            _example(
                "minus penkiolika laipsnių",
                "-15",
                _txt(
                    lang,
                    "Recognize - identify the temperature from Lithuanian",
                    "Atpazinimas - nustatykite temperatura is lietuviskos frazes",
                ),
            ),
            cls="grid grid-cols-1 gap-3 sm:grid-cols-2 mb-4",
        ),
    )


# ------------------------------------------------------------------
# Quiz area (HTMX target)
# ------------------------------------------------------------------


def quiz_area(
    question: str,
    feedback: Any | None = None,
    post_url: str = "/answer",
    label: str | None = None,
    lang: str = "en",
) -> Div:
    """Card with question + answer form, optional feedback alert above."""
    form = Form(
        Input(
            id="user_answer",
            name="user_answer",
            placeholder=_txt(
                lang,
                "Type your answer in Lithuanian...",
                "Irasykite atsakyma lietuviskai...",
            ),
            autofocus=True,
            autocomplete="off",
            spellcheck="false",
            autocorrect="off",
            cls="uk-input uk-form-large w-full",
        ),
        DivRAligned(
            Button(
                UkIcon("send", cls="mr-2"),
                _txt(lang, "Submit", "Pateikti"),
                type="submit",
                cls=(ButtonT.primary, "px-6 mt-4"),
            )
        ),
        hx_post=post_url,
        hx_target="#quiz-area",
        hx_swap="outerHTML",
    )

    label_text = label if label is not None else _txt(lang, "Practice", "Praktika")
    card = Card(
        CardHeader(
            DivFullySpaced(
                H3(_txt(lang, "Current Exercise", "Dabartine Uzduotis"), cls=TextT.lg),
                Label(label_text, cls=LabelT.primary),
            )
        ),
        CardBody(
            Div(
                P(
                    question,
                    cls="text-center text-xl font-medium p-4 rounded-lg mb-6",
                ),
                form,
                cls="space-y-4",
            )
        ),
        cls="shadow-lg border-t-4 border-t-primary",
    )

    parts: list[Any] = []
    if feedback:
        parts.append(feedback)
    parts.append(card)

    return Div(*parts, id="quiz-area")


# ------------------------------------------------------------------
# Feedback alerts (inline, not modals)
# ------------------------------------------------------------------

_CASE_LABELS: dict[str, dict[str, str]] = {
    "nominative": {"en": "nominative case (vardininkas)", "lt": "vardininkas"},
    "accusative": {"en": "accusative case (galininkas)", "lt": "galininkas"},
    "genitive": {"en": "genitive case (kilmininkas)", "lt": "kilmininkas"},
}
_TYPE_LABELS: dict[str, dict[str, str]] = {
    "kokia": {"en": "Kokia kaina?", "lt": "Kokia kaina?"},
    "kiek": {"en": "Kiek kainuoja?", "lt": "Kiek kainuoja?"},
    "whole_hour": {"en": "Whole hour", "lt": "Pilna valanda"},
    "half_past": {"en": "Half past", "lt": "Puse"},
    "quarter_past": {"en": "Quarter past", "lt": "Ketvirtis po"},
    "quarter_to": {"en": "Quarter to", "lt": "Be ketvircio"},
    "produce": {"en": "Produce (say the number)", "lt": "Kurimas (pasakyk skaiciu)"},
    "recognize": {
        "en": "Recognize (identify the number)",
        "lt": "Atpazinimas (atpazink skaiciu)",
    },
}
_GRAMMAR_HINTS: dict[str, dict[str, str]] = {
    "nominative": {
        "en": "Nominative: used when stating a price (Kokia kaina?).",
        "lt": "Vardininkas: vartojamas nurodant kaina (Kokia kaina?).",
    },
    "accusative": {
        "en": "Accusative: used when saying what something costs (Kiek kainuoja?).",
        "lt": "Galininkas: vartojamas sakant, kiek kas kainuoja (Kiek kainuoja?).",
    },
    "genitive": {
        "en": "Genitive: used with puse/ketvirtis (half past/quarter past).",
        "lt": "Kilmininkas: vartojamas su puse/ketvirtis.",
    },
}


def _grammar_hint_collapsible(hint_content: list[Any], lang: str) -> Details:
    """Wrap grammar hint content in a collapsible Details/Summary."""
    return Details(
        Summary(
            UkIcon("book-open", cls="inline mr-1", height=16, width=16),
            _txt(lang, "Grammar breakdown", "Gramatikos paaiskinimas"),
            cls="cursor-pointer text-sm text-base-content/60 hover:text-base-content "
            "list-none select-none",
        ),
        Div(*hint_content, cls="mt-2 space-y-1"),
        cls="mt-3",
    )


def _word_line(word: str, explanation: str) -> P:
    """Single word + explanation line for grammar breakdowns."""
    return P(
        Strong(word),
        Span(f" — {explanation}", cls="text-base-content/70"),
        cls="text-sm ml-2",
    )


_CASE_NAME_LABELS = {
    "nominative": {"en": "nominative", "lt": "vardininkas"},
    "accusative": {"en": "accusative", "lt": "galininkas"},
}
_CASE_NAME_NOM_ABBREV = {"en": "nom", "lt": "vard."}


def _price_grammar_hint(
    row: dict[str, Any],
    exercise_type: str | None,
    number_pattern: str | None,
    lang: str = "en",
) -> list[Any] | None:
    """Build word-by-word grammar breakdown for a price answer."""
    if not exercise_type or not row:
        return None

    lines: list[Any] = []
    n = row["number"]

    if exercise_type == "kokia":
        case_key = "nominative"
        num_word = row["kokia_kaina"]
        compound = row.get("kokia_kaina_compound")
        euro = row["euro_nom"]
    else:
        case_key = "accusative"
        num_word = row["kiek_kainuoja"]
        compound = row.get("kiek_kainuoja_compound")
        euro = row["euro_acc"]

    case_name = _CASE_NAME_LABELS[case_key][lang]
    nom_abbr = _CASE_NAME_NOM_ABBREV[lang]

    same_both = _txt(lang, "same in both cases", "tas pats abiem linksniais")
    tens_label = _txt(lang, "tens part", "desimciu dalis")
    ones_label = _txt(lang, "ones digit", "vienetu skaitmuo")
    euro_word = _txt(lang, "euro", "euras")

    # Number word(s)
    if number_pattern == "compound" and compound:
        lines.append(
            _word_line(
                num_word,
                f"{tens_label} ({n // 10 * 10}) — {same_both}",
            )
        )
        nom_ones = row.get("kokia_kaina_compound", compound)
        if exercise_type == "kiek":
            lines.append(
                _word_line(
                    compound,
                    f"{ones_label} ({n % 10}), {case_name} ({nom_abbr}: {nom_ones})",
                )
            )
        else:
            lines.append(_word_line(compound, f"{ones_label} ({n % 10}), {case_name}"))
    else:
        if exercise_type == "kiek":
            nom_form = row["kokia_kaina"]
            if nom_form != num_word:
                if lang == "lt":
                    explanation = f"{n} {case_name} ({nom_abbr}: {nom_form})"
                else:
                    explanation = f"{case_name} of {n} ({nom_abbr}: {nom_form})"
                lines.append(_word_line(num_word, explanation))
            else:
                lines.append(_word_line(num_word, f"{n} — {same_both}"))
        else:
            lines.append(_word_line(num_word, f"{n}, {case_name}"))

    # Euro word
    if exercise_type == "kiek":
        nom_euro = row["euro_nom"]
        if nom_euro != euro:
            lines.append(
                _word_line(euro, f"{euro_word}, {case_name} ({nom_abbr}: {nom_euro})")
            )
        else:
            lines.append(_word_line(euro, f"{euro_word} — {same_both}"))
    else:
        lines.append(_word_line(euro, f"{euro_word}, {case_name}"))

    return lines


def _time_grammar_hint(
    exercise_type: str | None,
    hour: int | None,
    lang: str = "en",
) -> list[Any] | None:
    """Build word-by-word grammar breakdown for a time answer."""
    if not exercise_type or hour is None:
        return None

    lines: list[Any] = []
    nh = _next_hour(hour)

    nom_abbr = _CASE_NAME_NOM_ABBREV[lang]
    hour_word_note = _txt(
        lang, "hour (always nominative)", "valanda (visada vardininkas)"
    )

    def _nom_fem_for(n: int) -> str:
        return _txt(
            lang,
            f"ordinal for {n}, nominative feminine",
            f"{n} kelintinis, moteriska gimine, vardininkas",
        )

    def _genitive_of(n: int, nom: str) -> str:
        return _txt(
            lang,
            f"genitive of {n} (nom: {nom})",
            f"{n} kilmininkas ({nom_abbr}: {nom})",
        )

    def _nominative_of(n: int) -> str:
        return _txt(lang, f"nominative of {n}", f"{n} vardininkas")

    def _next_hour_note(kind_en: str, kind_lt: str) -> str:
        prefix = _txt(lang, kind_en, kind_lt)
        tail = _txt(
            lang,
            f"next hour is {nh} ({hour}→{nh})",
            f"kita valanda - {nh} ({hour}→{nh})",
        )
        return f"{prefix} — {tail}"

    if exercise_type == "whole_hour":
        nom = ORDINALS_NOM[hour]
        lines.append(_word_line(nom.capitalize(), _nom_fem_for(hour)))
        lines.append(_word_line("valanda", hour_word_note))

    elif exercise_type == "half_past":
        gen = ORDINALS_GEN[nh]
        nom = ORDINALS_NOM[nh]
        lines.append(_word_line("Pusė", _next_hour_note("half", "puse")))
        lines.append(_word_line(gen, _genitive_of(nh, nom)))

    elif exercise_type == "quarter_past":
        gen = ORDINALS_GEN[nh]
        nom = ORDINALS_NOM[nh]
        lines.append(
            _word_line("Ketvirtis", _next_hour_note("quarter past", "ketvirtis po"))
        )
        lines.append(_word_line(gen, _genitive_of(nh, nom)))

    elif exercise_type == "quarter_to":
        nom = ORDINALS_NOM[nh]
        lines.append(
            _word_line(
                "Be ketvirčio",
                _next_hour_note("quarter to", "be ketvircio"),
            )
        )
        lines.append(_word_line(nom, _nominative_of(nh)))

    return lines


def _exercise_context_text(
    exercise_type: str | None,
    grammatical_case: str | None,
    lang: str,
) -> str:
    """One-line description of what this exercise tested."""
    parts = []
    if exercise_type:
        parts.append(_TYPE_LABELS.get(exercise_type, {}).get(lang, exercise_type))
    if grammatical_case:
        parts.append(_CASE_LABELS.get(grammatical_case, {}).get(lang, grammatical_case))
    return " — ".join(parts)


def feedback_correct(
    user_answer: str,
    exercise_type: str | None = None,
    grammatical_case: str | None = None,
    question: str | None = None,
    lang: str = "en",
) -> Div:
    """Green inline alert for correct answer."""
    ctx = _exercise_context_text(exercise_type, grammatical_case, lang)
    return Div(
        DivLAligned(
            UkIcon("check-circle", cls="text-success mr-2"),
            Div(
                P(
                    _txt(lang, "Correct!", "Teisingai!"),
                    cls=(TextT.bold, "text-success"),
                ),
                *(
                    [P(question, cls="text-base-content/70 text-sm italic")]
                    if question
                    else []
                ),
                P(
                    f"{_txt(lang, 'Your answer', 'Jusu atsakymas')}: {user_answer}",
                    cls=TextT.sm,
                ),
                *([P(ctx, cls="text-base-content/60 text-xs mt-1")] if ctx else []),
            ),
        ),
        cls="mb-4 p-4 rounded-lg border-2 border-success/40 bg-success/20 text-base-content",
    )


def feedback_incorrect(
    user_answer: str,
    correct_answer: str,
    diff_user: str,
    diff_correct: str,
    exercise_type: str | None = None,
    grammatical_case: str | None = None,
    number_pattern: str | None = None,
    row: dict[str, Any] | None = None,
    hour: int | None = None,
    question: str | None = None,
    lang: str = "en",
) -> Div:
    """Red inline alert with diff highlighting and grammar context."""
    ctx = _exercise_context_text(exercise_type, grammatical_case, lang)
    hint = _GRAMMAR_HINTS.get(grammatical_case or "", {}).get(lang)

    # Build grammar breakdown (price or time)
    grammar_lines = None
    if row is not None:
        grammar_lines = _price_grammar_hint(row, exercise_type, number_pattern, lang)
    elif hour is not None:
        grammar_lines = _time_grammar_hint(exercise_type, hour, lang)

    return Div(
        DivLAligned(
            UkIcon("x-circle", cls="text-error mr-2", height=24, width=24),
            Div(
                P(
                    _txt(lang, "Not quite right", "Netikslu"),
                    cls=(TextT.bold, "text-error"),
                ),
                *(
                    [P(question, cls="text-base-content/70 text-sm italic")]
                    if question
                    else []
                ),
            ),
        ),
        Div(
            P(
                f"{_txt(lang, 'Your answer', 'Jusu atsakymas')}:",
                cls=(TextT.bold, "text-sm mt-2"),
            ),
            P(NotStr(diff_user), cls="ml-4"),
            P(
                f"{_txt(lang, 'Correct answer', 'Teisingas atsakymas')}:",
                cls=(TextT.bold, "text-sm mt-2"),
            ),
            P(NotStr(diff_correct), cls="ml-4"),
            cls="mt-2",
        ),
        *(
            [
                Div(
                    P(ctx, cls="text-sm font-medium text-base-content/70"),
                    *(
                        [P(hint, cls="text-xs text-base-content/60 italic mt-1")]
                        if hint
                        else []
                    ),
                    *(
                        [_grammar_hint_collapsible(grammar_lines, lang)]
                        if grammar_lines
                        else []
                    ),
                    cls="border-t border-base-content/10 pt-3 mt-3",
                )
            ]
            if ctx
            else []
        ),
        cls="mb-4 p-4 rounded-lg border-2 border-error/40 bg-error/20 text-base-content",
    )


# ------------------------------------------------------------------
# Stats panel (sidebar / OOB)
# ------------------------------------------------------------------


def _stat_metric(icon: str, value: str, label: str, color: str = "text-primary") -> Div:
    return Div(
        DivCentered(
            UkIcon(icon, cls=f"{color} mb-1", height=24, width=24),
            H4(
                value,
                cls=(TextT.xl, TextT.bold, f"text-center text-2xl {color}"),
            ),
            P(label, cls=TextPresets.muted_sm),
        ),
        cls="p-3 rounded-md",
    )


def _accuracy_bar(accuracy: float, lang: str = "en") -> Div:
    color = (
        "bg-error" if accuracy < 60 else "bg-warning" if accuracy < 80 else "bg-success"
    )
    return Div(
        P(
            f"{_txt(lang, 'Accuracy', 'Tikslumas')}: {accuracy:.1f}%",
            cls=(TextT.bold, "mb-1"),
        ),
        Progress(
            value=int(min(100, accuracy)),
            max=100,
            cls=f"h-3 rounded-full {color}",
        ),
        cls="mt-4 space-y-2",
    )


_ARM_LABELS_LT: dict[str, str] = {
    # exercise_types
    "produce": "Kūrimas",
    "recognize": "Atpažinimas",
    "kokia": "Kokia kaina?",
    "kiek": "Kiek kainuoja?",
    "whole_hour": "Pilna valanda",
    "half_past": "Pusė",
    "quarter_past": "Ketvirtis po",
    "quarter_to": "Be ketvirčio",
    # number_patterns
    "single_digit": "Vienaženkliai",
    "teens": "Paaugliai (10-19)",
    "round_ten": "Apvali dešimtis",
    "compound": "Sudėtiniai",
    # grammatical_cases
    "nominative": "Vardininkas",
    "accusative": "Galininkas",
    "genitive": "Kilmininkas",
    # sign
    "positive": "Teigiamas",
    "negative": "Neigiamas",
}

_CATEGORY_LABELS_LT: dict[str, str] = {
    "Exercise Types": "Užduočių tipai",
    "Number Patterns": "Skaičių modeliai",
    "Grammatical Cases": "Linksniai",
    "Hour Patterns": "Valandų modeliai",
    "Pronouns": "Įvardžiai",
    "Sign": "Ženklas",
    "Sign (+/-)": "Ženklas (+/-)",
}


def _fmt_arm_name(raw: str, lang: str) -> str:
    """Display a weak-area/performance arm name, localized when lang='lt'."""
    if _is_lt(lang) and raw in _ARM_LABELS_LT:
        return _ARM_LABELS_LT[raw]
    # Hour patterns like "hour_3" — keep number, localize word.
    if raw.startswith("hour_"):
        n = raw.removeprefix("hour_")
        if _is_lt(lang):
            return f"{n} valanda"
        return f"Hour {n}"
    return raw.replace("_", " ").title()


def _fmt_category(raw: str, lang: str) -> str:
    if _is_lt(lang):
        return _CATEGORY_LABELS_LT.get(raw, raw)
    return raw


def _weak_area_item(area: dict[str, Any], lang: str = "en") -> Li:
    rate = area["success_rate"] * 100
    color = "bg-error" if rate < 60 else "bg-warning" if rate < 80 else "bg-success"
    return Li(
        Div(
            P(
                _fmt_arm_name(area["name"], lang),
                cls=TextT.medium,
            ),
            Progress(value=int(rate), max=100, cls=f"h-2 rounded-full {color}"),
            P(f"{rate:.1f}%", cls=TextPresets.muted_sm),
            cls="w-full",
        ),
        cls="mb-3",
    )


def _weak_areas_section(
    weak_areas: dict[str, list[dict[str, Any]]],
    lang: str = "en",
) -> Card:
    if not weak_areas:
        body = DivCentered(
            UkIcon("target", height=40, width=40, cls="text-muted mb-2"),
            P(
                _txt(lang, "Complete more exercises", "Atlikite daugiau uzduociu"),
                cls=TextPresets.muted_sm,
            ),
            cls="py-8",
        )
    else:
        sections = []
        for cat, areas in weak_areas.items():
            sections.append(
                Div(
                    H4(
                        _fmt_category(cat, lang),
                        cls=(TextT.bold, "mb-2"),
                    ),
                    Ul(
                        *[_weak_area_item(a, lang=lang) for a in areas],
                        cls="space-y-2",
                    ),
                    cls="mb-4",
                )
            )
        body = Div(*sections)

    return Card(
        CardHeader(
            H3(_txt(lang, "Areas to Improve", "Tobulintinos Sritys"), cls=TextT.lg),
            Subtitle(
                _txt(lang, "Focus on these areas", "Skirkite demesi sioms sritims")
            ),
        ),
        CardBody(body),
        cls="shadow-lg border-t-4 border-t-warning h-full",
    )


def _history_entry(
    entry: dict[str, Any], idx: int, total: int, lang: str = "en"
) -> Div:
    correct = entry["correct"]
    diff_u, diff_c = highlight_diff(entry["answer"], entry["true_answer"], correct)
    return Div(
        Div(
            UkIcon(
                "check-circle" if correct else "x-circle",
                cls=f"{'text-success' if correct else 'text-error'} mr-2",
            ),
            Span(f"Q{total - idx}", cls=(TextT.bold, "mr-2")),
            Span(entry["question"], cls=TextT.medium),
            cls="flex items-center",
        ),
        Div(
            P(
                f"{_txt(lang, 'Your answer', 'Jusu atsakymas')}:",
                cls=(TextT.gray, TextT.bold, "text-sm mt-2"),
            ),
            P(NotStr(diff_u), cls="ml-4"),
            *(
                [
                    P(
                        f"{_txt(lang, 'Correct answer', 'Teisingas atsakymas')}:",
                        cls=(TextT.gray, TextT.bold, "text-sm mt-2"),
                    ),
                    P(NotStr(diff_c), cls="ml-4"),
                ]
                if not correct
                else []
            ),
            cls="ml-8 mt-1",
        ),
        cls=f"border-l-4 {'border-success' if correct else 'border-error'} pl-4 py-2 mb-4",
    )


def _history_card(history: list[dict[str, Any]], lang: str = "en") -> Card:
    total = len(history)
    if history:
        items = [
            _history_entry(e, i, total, lang=lang)
            for i, e in enumerate(reversed(history[-5:]))
        ]
        body = Div(*items)
    else:
        body = DivCentered(
            UkIcon("history", height=40, width=40, cls="text-muted mb-2"),
            P(
                _txt(lang, "No history yet", "Istorijos dar nera"),
                cls=TextPresets.muted_lg,
            ),
            P(
                _txt(
                    lang,
                    "Your exercise history will appear here",
                    "Cia bus rodoma jusu uzduociu istorija",
                ),
                cls=TextPresets.muted_sm,
            ),
            cls="py-16",
        )
    return Card(
        CardHeader(
            DivFullySpaced(
                H3(
                    _txt(lang, "Recent Exercises", "Pastarosios uzduotys"),
                    cls=TextT.lg,
                ),
                A(
                    _txt(lang, "View All", "Ziureti Viska"),
                    href="/stats",
                    cls="uk-btn uk-btn-ghost",
                ),
            ),
            Subtitle(
                _txt(
                    lang,
                    "Review your previous exercises",
                    "Perziurekite ankstesnes uzduotis",
                )
            ),
        ),
        CardBody(body, cls="max-h-[400px] overflow-y-auto pr-2"),
        cls="shadow-lg border-t-4 border-t-accent h-full",
    )


def stats_panel(
    stats: dict[str, Any],
    history: list[dict[str, Any]],
    *,
    oob: bool = False,
    lang: str = "en",
) -> Div:
    """Full right-side stats panel for OOB swap."""
    metrics = Grid(
        _stat_metric(
            "list", str(stats["total"]), _txt(lang, "Total", "Is Viso"), "text-primary"
        ),
        _stat_metric(
            "check",
            str(stats["correct"]),
            _txt(lang, "Correct", "Teisingi"),
            "text-success",
        ),
        _stat_metric(
            "x",
            str(stats["incorrect"]),
            _txt(lang, "Incorrect", "Neteisingi"),
            "text-error",
        ),
        _stat_metric(
            "flame",
            str(stats["current_streak"]),
            _txt(lang, "Streak", "Serija"),
            "text-warning",
        ),
        cols=4,
        cols_sm=2,
        gap=4,
        cls="mb-6",
    )
    weak = _weak_areas_section(stats.get("weak_areas", {}), lang=lang)
    hist = _history_card(history, lang=lang)

    kwargs: dict[str, Any] = {"id": "stats-panel"}
    if oob:
        kwargs["hx_swap_oob"] = "true"
    return Div(
        metrics,
        _accuracy_bar(stats["accuracy"], lang=lang),
        Div(cls="mt-6"),
        Grid(
            Div(weak, cls="h-full col-span-1"),
            Div(hist, cls="h-full col-span-1"),
            cols_md=2,
            cols_sm=1,
            gap=6,
        ),
        **kwargs,
    )


# ------------------------------------------------------------------
# Performance-by-category card (stats page)
# ------------------------------------------------------------------


def _perf_by_category(
    category_data: dict[str, dict[str, int]],
    title: str,
    lang: str = "en",
) -> Card:
    items = []
    for key, s in category_data.items():
        total = s["correct"] + s["incorrect"]
        rate = (s["correct"] / total * 100) if total else 0
        color = "bg-error" if rate < 60 else "bg-warning" if rate < 80 else "bg-success"
        items.append(
            Div(
                P(_fmt_arm_name(key, lang), cls=TextT.medium),
                Progress(
                    value=int(rate),
                    max=100,
                    cls=f"h-2 rounded-full {color}",
                ),
                P(
                    f"{rate:.1f}% ({s['correct']}/{total})",
                    cls=TextPresets.muted_sm,
                ),
                cls="mb-3",
            )
        )
    return Card(
        CardHeader(
            H3(title, cls=TextT.lg),
            Subtitle(
                _txt(lang, "Performance by category", "Rezultatai pagal kategorija")
            ),
        ),
        CardBody(*items),
        cls="shadow-lg border-t-4 border-t-primary h-full",
    )


# ------------------------------------------------------------------
# Full-page views
# ------------------------------------------------------------------


def _module_stats_section(
    title: str,
    stats: dict[str, Any],
    session: dict[str, Any],
    perf_key: str,
    history_key: str,
    border_color: str = "border-t-secondary",
    lang: str = "en",
) -> list[Any]:
    """Build stats cards for a single module (prices or time)."""
    stats_card = Card(
        CardHeader(
            H3(title, cls=TextT.lg),
            Subtitle(
                _txt(lang, "Track your learning journey", "Sekite savo mokymosi kelia")
            ),
        ),
        CardBody(
            Grid(
                _stat_metric(
                    "list",
                    str(stats["total"]),
                    _txt(lang, "Total", "Is Viso"),
                    "text-primary",
                ),
                _stat_metric(
                    "check",
                    str(stats["correct"]),
                    _txt(lang, "Correct", "Teisingi"),
                    "text-success",
                ),
                _stat_metric(
                    "x",
                    str(stats["incorrect"]),
                    _txt(lang, "Incorrect", "Neteisingi"),
                    "text-error",
                ),
                _stat_metric(
                    "flame",
                    str(stats["current_streak"]),
                    _txt(lang, "Streak", "Serija"),
                    "text-warning",
                ),
                cols=4,
                cols_sm=2,
                gap=4,
                cls="mb-4",
            ),
            _accuracy_bar(stats["accuracy"], lang=lang),
        ),
        cls=f"shadow-lg border-t-4 {border_color} h-full",
    )

    weak_card = _weak_areas_section(stats.get("weak_areas", {}), lang=lang)

    perf_cards: list[Any] = []
    perf = session.get(perf_key, {})
    perf_categories = [
        ("exercise_types", "Exercise Types"),
        ("number_patterns", "Number Patterns"),
        ("grammatical_cases", "Grammatical Cases"),
    ]
    if perf_key == "time_performance":
        perf_categories[1] = ("hour_patterns", "Hour Patterns")
    if perf_key == "age_performance":
        perf_categories = [
            ("exercise_types", "Exercise Types"),
            ("number_patterns", "Number Patterns"),
            ("pronouns", "Pronouns"),
        ]
    if perf_key == "weather_performance":
        perf_categories = [
            ("exercise_types", "Exercise Types"),
            ("number_patterns", "Number Patterns"),
            ("sign", "Sign (+/-)"),
        ]
    for key, cat_title in perf_categories:
        if perf.get(key):
            perf_cards.append(
                _perf_by_category(perf[key], _fmt_category(cat_title, lang), lang=lang)
            )

    detail_section = (
        Grid(*perf_cards, cols_md=1, cols_lg=2, cols_xl=3, gap=6)
        if perf_cards
        else DivCentered(
            UkIcon("info", height=40, width=40, cls="text-muted mb-2"),
            P(
                _txt(
                    lang,
                    "Complete more exercises to see detailed performance",
                    "Atlikite daugiau uzduociu, kad matytumete issamesnius rezultatus",
                ),
                cls=TextPresets.muted_lg,
            ),
            cls="py-8 bg-base-200 rounded-lg mt-4",
        )
    )

    history = session.get(history_key, [])
    total = len(history)
    if history:
        hist_items = [
            _history_entry(e, i, total, lang=lang)
            for i, e in enumerate(reversed(history))
        ]
        hist_body = Div(*hist_items)
    else:
        hist_body = DivCentered(
            P(
                _txt(lang, "No history yet", "Istorijos dar nera"),
                cls=TextPresets.muted_lg,
            ),
            cls="py-8",
        )

    hist_card = Card(
        CardHeader(
            H3(_txt(lang, "History", "Istorija"), cls=TextT.lg),
            Subtitle(_txt(lang, "Your exercises", "Jusu uzduotys")),
        ),
        CardBody(hist_body, cls="max-h-[400px] overflow-y-auto pr-2"),
        cls="shadow-lg border-t-4 border-t-accent h-full",
    )

    return [
        Div(stats_card, cls="mt-6"),
        Div(weak_card, cls="mt-6"),
        Div(detail_section, cls="mt-4"),
        Div(hist_card, cls="mt-6"),
    ]


def stats_page_content(
    stats: dict[str, Any],
    session: dict[str, Any],
    time_stats: dict[str, Any] | None = None,
    n20_stats: dict[str, Any] | None = None,
    n99_stats: dict[str, Any] | None = None,
    age_stats: dict[str, Any] | None = None,
    weather_stats: dict[str, Any] | None = None,
    lang: str = "en",
) -> Container:
    """Full stats page body with all module sections."""
    sections: list[Any] = [
        H2(_txt(lang, "Your Statistics", "Jusu Statistika"), cls=TextT.xl),
        P(
            _txt(lang, "Track your learning progress", "Sekite savo mokymosi pazanga"),
            cls=TextPresets.muted_lg,
        ),
    ]

    # Numbers 1-20 stats
    if n20_stats is not None:
        sections.append(
            H3(_txt(lang, "Numbers 1-20", "Skaiciai 1-20"), cls=(TextT.lg, "mt-8 mb-0"))
        )
        sections.extend(
            _module_stats_section(
                _txt(lang, "Numbers 1-20 Progress", "Skaiciu 1-20 Pazanga"),
                n20_stats,
                session,
                perf_key="n20_performance",
                history_key="n20_history",
                border_color="border-t-success",
                lang=lang,
            )
        )

    # Numbers 1-99 stats
    if n99_stats is not None:
        sections.append(
            H3(
                _txt(lang, "Numbers 1-99", "Skaiciai 1-99"),
                cls=(TextT.lg, "mt-10 mb-0"),
            )
        )
        sections.extend(
            _module_stats_section(
                _txt(lang, "Numbers 1-99 Progress", "Skaiciu 1-99 Pazanga"),
                n99_stats,
                session,
                perf_key="n99_performance",
                history_key="n99_history",
                border_color="border-t-info",
                lang=lang,
            )
        )

    # Age stats
    if age_stats is not None:
        sections.append(
            H3(
                _txt(lang, "Age Exercises", "Uzduotys apie amziu"),
                cls=(TextT.lg, "mt-10 mb-0"),
            )
        )
        sections.extend(
            _module_stats_section(
                _txt(lang, "Age Progress", "Amziaus Pazanga"),
                age_stats,
                session,
                perf_key="age_performance",
                history_key="age_history",
                border_color="border-t-warning",
                lang=lang,
            )
        )

    # Weather stats
    if weather_stats is not None:
        sections.append(
            H3(
                _txt(lang, "Weather Exercises", "Uzduotys apie ora"),
                cls=(TextT.lg, "mt-10 mb-0"),
            )
        )
        sections.extend(
            _module_stats_section(
                _txt(lang, "Weather Progress", "Oro Pazanga"),
                weather_stats,
                session,
                perf_key="weather_performance",
                history_key="weather_history",
                border_color="border-t-error",
                lang=lang,
            )
        )

    # Price stats
    sections.append(
        H3(
            _txt(lang, "Price Exercises", "Uzduotys apie kainas"),
            cls=(TextT.lg, "mt-10 mb-0"),
        )
    )
    sections.extend(
        _module_stats_section(
            _txt(lang, "Price Progress", "Kainu Pazanga"),
            stats,
            session,
            perf_key="performance",
            history_key="history",
            border_color="border-t-secondary",
            lang=lang,
        )
    )

    # Time stats
    if time_stats is not None:
        sections.append(
            H3(
                _txt(lang, "Time Exercises", "Uzduotys apie laika"),
                cls=(TextT.lg, "mt-10 mb-0"),
            )
        )
        sections.extend(
            _module_stats_section(
                _txt(lang, "Time Progress", "Laiko Pazanga"),
                time_stats,
                session,
                perf_key="time_performance",
                history_key="time_history",
                border_color="border-t-info",
                lang=lang,
            )
        )

    sections.append(
        A(
            UkIcon("arrow-left", cls="mr-2"),
            _txt(lang, "Back to Practice", "Atgal i Praktika"),
            href="/",
            cls="uk-btn uk-btn-primary mt-8",
        )
    )

    return Container(*sections, cls=(ContainerT.xl, "px-8 py-8"))


def about_page_content(lang: str = "en") -> Container:
    return Container(
        H2(_txt(lang, "About This App", "Apie Sia Programa"), cls=TextT.xl),
        P(
            _txt(
                lang,
                "Practice Lithuanian number expressions with adaptive exercises!",
                "Mokykites kalbeti apie skaicius su adaptyviomis uzduotimis!",
            ),
            cls=TextPresets.muted_lg,
        ),
        P(
            _txt(
                lang,
                "This app helps you practice Lithuanian numbers, prices, and times through interactive exercises. An adaptive learning system uses Thompson sampling to target your weak areas.",
                "Si programa skirta mokytis kalbeti apie skaicius, kainas ir laika naudojant interaktyvias uzduotis. Adaptyvi mokymosi sistema naudoja Thompson atranka silpnoms vietoms stiprinti.",
            ),
            cls="mt-4",
        ),
        H3(
            _txt(lang, "Number Exercises", "Uzduotys apie skaicius"),
            cls=(TextT.lg, "mt-6"),
        ),
        P(
            _txt(
                lang,
                "Two modules for building number vocabulary:",
                "Du moduliai skaiciu zodynui plesti:",
            ),
            cls="mt-2",
        ),
        Ul(
            Li(
                Strong(_txt(lang, "Numbers 1-20", "Skaiciai 1-20")),
                _txt(
                    lang,
                    " - Learn the basic (often irregular) number words.",
                    " - Mokykites pagrindiniu (daznai netaisyklingu) skaiciaus zodziu.",
                ),
            ),
            Li(
                Strong(_txt(lang, "Numbers 1-99", "Skaiciai 1-99")),
                _txt(
                    lang,
                    " - All numbers including decades and compounds.",
                    " - Visi skaiciai, iskaitant desimtis ir sudetinius.",
                ),
            ),
            cls="list-disc ml-6 mt-2 space-y-2",
        ),
        P(
            _txt(
                lang,
                "Each module has two exercise types: ",
                "Kiekvienas modulis turi du uzduociu tipus: ",
            ),
            Strong(_txt(lang, "produce", "kurimas")),
            _txt(
                lang,
                " (say the number in Lithuanian) and ",
                " (pasakykite skaiciu lietuviskai) ir ",
            ),
            Strong(_txt(lang, "recognize", "atpazinimas")),
            _txt(
                lang,
                " (identify the number from Lithuanian).",
                " (atpazinkite skaiciu is lietuviskos israiskos).",
            ),
            cls="mt-2",
        ),
        H3(_txt(lang, "Age Exercises", "Uzduotys apie amziu"), cls=(TextT.lg, "mt-6")),
        P(
            _txt(
                lang,
                "Practice expressing ages using dative pronouns (Man, Tau, Jam, Jai) with the correct year word (metai/metu).",
                "Praktikuokite amziu israiskas su naudininko ivardziais (Man, Tau, Jam, Jai) ir tinkamu zodziu metai/metu.",
            ),
            cls="mt-2",
        ),
        Ul(
            Li(
                Strong(_txt(lang, "Produce", "Kurimas")),
                _txt(
                    lang,
                    ' - given an English prompt like "He is 25 years old.", type the Lithuanian phrase.',
                    ' - pateikus angliska uzduoti, pvz., "He is 25 years old.", irasykite lietuviska fraze.',
                ),
            ),
            Li(
                Strong(_txt(lang, "Recognize", "Atpazinimas")),
                _txt(
                    lang,
                    " - given a Lithuanian age phrase, identify the age as a number.",
                    " - pateikus lietuviska amziaus fraze, nustatykite amziu skaiciumi.",
                ),
            ),
            cls="list-disc ml-6 mt-2 space-y-2",
        ),
        H3(
            _txt(lang, "Weather Exercises", "Uzduotys apie ora"), cls=(TextT.lg, "mt-6")
        ),
        P(
            _txt(
                lang,
                'Practice expressing temperatures with the word "laipsnis" (degree), which declines like other Lithuanian nouns:',
                'Praktikuokite temperaturos israiskas su zodziu "laipsnis", kuris linksniuojamas kaip ir kiti lietuviski daiktavardziai:',
            ),
            cls="mt-2",
        ),
        Ul(
            Li(
                Strong(_txt(lang, "Produce", "Kurimas")),
                _txt(
                    lang,
                    " - given a temperature like 25C, type the Lithuanian phrase.",
                    " - pateikus temperatura, pvz., 25C, irasykite lietuviska fraze.",
                ),
            ),
            Li(
                Strong(_txt(lang, "Recognize", "Atpazinimas")),
                _txt(
                    lang,
                    " - given a Lithuanian temperature phrase, identify the number.",
                    " - pateikus lietuviska temperaturos fraze, nustatykite skaiciu.",
                ),
            ),
            cls="list-disc ml-6 mt-2 space-y-2",
        ),
        P(
            _txt(
                lang,
                "Negative temperatures (down to -20) add ",
                "Neigiamos temperaturos (iki -20) prideda ",
            ),
            Em("minus"),
            _txt(lang, " before the number word.", " pries skaiciaus zodi."),
            cls="mt-2",
        ),
        H3(
            _txt(lang, "Price Exercises", "Uzduotys apie kainas"),
            cls=(TextT.lg, "mt-6"),
        ),
        P(_txt(lang, "Two exercise types:", "Du uzduociu tipai:"), cls="mt-2"),
        Ul(
            Li(
                Strong("Kokia kaina?"),
                _txt(
                    lang,
                    " (What is the price?) - Nominative case (vardininkas). State the price directly.",
                    " (Kokia kaina?) - Vardininkas. Kaina nurodoma tiesiogiai.",
                ),
            ),
            Li(
                Strong("Kiek kainuoja?"),
                _txt(
                    lang,
                    " (How much does it cost?) - Accusative case (galininkas). The number changes form.",
                    " (Kiek kainuoja?) - Galininkas. Skaiciaus forma keiciasi.",
                ),
            ),
            cls="list-disc ml-6 mt-2 space-y-2",
        ),
        H3(_txt(lang, "Time Exercises", "Uzduotys apie laika"), cls=(TextT.lg, "mt-6")),
        P(_txt(lang, "Four exercise types:", "Keturi uzduociu tipai:"), cls="mt-2"),
        Ul(
            Li(
                Strong(_txt(lang, "Whole hours", "Pilnos valandos")),
                _txt(
                    lang,
                    " - Feminine ordinal + valanda (e.g., ",
                    " - Moteriskos g. kelintinis + valanda (pvz., ",
                ),
                Em("Trečia valanda"),
                ").",
            ),
            Li(
                Strong(_txt(lang, "Half past", "Puse")),
                _txt(
                    lang,
                    " - Puse + genitive of next hour (e.g., ",
                    " - Puse + kitos valandos kilmininkas (pvz., ",
                ),
                Em("Pusė ketvirtos"),
                ").",
            ),
            Li(
                Strong(_txt(lang, "Quarter past", "Ketvirtis po")),
                _txt(
                    lang,
                    " - Ketvirtis + genitive of next hour (e.g., ",
                    " - Ketvirtis + kitos valandos kilmininkas (pvz., ",
                ),
                Em("Ketvirtis antros"),
                ").",
            ),
            Li(
                Strong(_txt(lang, "Quarter to", "Be ketvircio")),
                _txt(
                    lang,
                    " - Be ketvircio + nominative of next hour (e.g., ",
                    " - Be ketvircio + kitos valandos vardininkas (pvz., ",
                ),
                Em("Be ketvirčio trečia"),
                ").",
            ),
            cls="list-disc ml-6 mt-2 space-y-2",
        ),
        P(
            _txt(
                lang,
                "Practice regularly to improve your Lithuanian language skills!",
                "Gerinkite lietuviu kalbos igudzius per reguliaria praktika!",
            ),
            cls="mt-6",
        ),
        P(
            _txt(lang, "Made by ", "Sukure "),
            A(
                "Jonathan Whitmore",
                href="https://jonathanwhitmore.com",
                cls="underline",
                target="_blank",
            ),
            ".",
            cls="mt-6 text-base-content/60 text-sm",
        ),
        A(
            UkIcon("arrow-left", cls="mr-2"),
            _txt(lang, "Back to Practice", "Atgal i Praktika"),
            href="/",
            cls="uk-btn uk-btn-primary mt-6",
        ),
        cls=(ContainerT.xl, "px-8 py-8"),
    )
