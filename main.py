"""Lithuanian Price Exercise App — adaptive quiz with HTMX partials."""

import logging
import os
import secrets
from typing import Any

from adaptive import AdaptiveLearning
from age_engine import AgeEngine
from auth import QuizOAuth, auth_client, init_db_tables, save_progress
from fasthtml.common import *
from fastlite import database
from i18n import UI_LANGUAGE_KEY, normalize_ui_lang, tr, ui_lang_from_session
from monsterui.all import *
from number_engine import NumberEngine
from quiz import ExerciseEngine, highlight_diff, number_pattern
from thompson import sample_weakest as _sample_weakest
from time_engine import TimeEngine
from ui import (
    about_page_content,
    age_examples_section,
    examples_section,
    feedback_correct,
    feedback_incorrect,
    landing_page_content,
    login_page_content,
    number_examples_section,
    page_shell,
    quiz_area,
    stats_page_content,
    stats_panel,
    time_examples_section,
    weather_examples_section,
)
from weather_engine import WeatherEngine

log = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Data & services (loaded once at startup)
# ------------------------------------------------------------------

_db = database("lithuanian_data.db")
init_db_tables()
ALL_ROWS: list[dict[str, Any]] = list(_db.t["numbers"].rows)

adaptive = AdaptiveLearning()
price_rows = [r for r in ALL_ROWS if r["number"] >= 1]
engine = ExerciseEngine(price_rows, adaptive)
time_engine = TimeEngine()

number_engine = NumberEngine(ALL_ROWS)

age_rows = [r for r in ALL_ROWS if r["number"] >= 2]
age_engine = AgeEngine(age_rows)

weather_rows = [r for r in ALL_ROWS if r["number"] >= 0]
weather_engine = WeatherEngine(weather_rows)

# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------

_favicon = Link(
    rel="icon",
    href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🇱🇹</text></svg>",
)
_goatcounter = Script(
    src="//gc.zgo.at/count.js",
    data_goatcounter="https://jbwhit.goatcounter.com/count",
    async_=True,
)

_custom_css = Style("""\
.module-card {
    transition: transform 0.4s cubic-bezier(0.22, 1, 0.36, 1),
                box-shadow 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}
.module-card:hover {
    transform: translateY(-6px);
    box-shadow: 0 20px 50px -12px rgba(0, 0, 0, 0.12),
                0 4px 12px rgba(0, 0, 0, 0.05);
}
""")


def _not_found(req, exc) -> Any:
    session = req.scope.get("session", {}) if hasattr(req, "scope") else {}
    if not isinstance(session, dict):
        session = {}
    lang = ui_lang_from_session(session)
    return page_shell(
        Container(
            DivCentered(
                Span("🇱🇹", cls="text-6xl mb-4"),
                H2(
                    tr(lang, "Page Not Found", "Puslapis Nerastas"),
                    cls=(TextT.xl, TextT.bold),
                ),
                P(
                    tr(
                        lang,
                        "The page you're looking for doesn't exist.",
                        "Jusu ieskomas puslapis neegzistuoja.",
                    ),
                    cls=TextPresets.muted_lg,
                ),
                A(
                    UkIcon("arrow-left", cls="mr-2"),
                    tr(lang, "Back to Home", "Atgal i Pradzia"),
                    href="/",
                    cls="uk-btn uk-btn-primary mt-6",
                ),
                cls="min-h-[40vh]",
            ),
            cls=(ContainerT.xl, "px-8 py-16"),
        ),
        user_name=session.get("user_name"),
        lang=lang,
        diacritic_tolerant=_is_diacritic_tolerant(session),
        current_path=req.url.path if req else "/",
    )


app, rt = fast_app(
    hdrs=[*Theme.green.headers(daisy=True), _custom_css, _favicon, _goatcounter],
    secret_key=os.environ.get("LQ_SECRET_KEY") or secrets.token_urlsafe(32),
    title="Lithuanian Price Quiz",
    exception_handlers={404: _not_found},
)

oauth = QuizOAuth(app, auth_client)

# ------------------------------------------------------------------
# Session helpers
# ------------------------------------------------------------------

_SESSION_HISTORY_LIMIT = 5
_DIACRITIC_MODE_KEY = "diacritic_tolerant"


def _is_diacritic_tolerant(session: dict[str, Any]) -> bool:
    """Return whether diacritic-tolerant answer checking is enabled."""
    return bool(session.get(_DIACRITIC_MODE_KEY, False))


_LEGACY_NUMBER_PREFIXES = ("n20_", "n99_")


def _strip_legacy_number_keys(session: dict[str, Any]) -> None:
    """Remove pre-consolidation n20_/n99_ session keys.

    Anonymous users (no OAuth) never flow through auth.load_progress, so
    their cookie would keep these keys forever otherwise. First call per
    request cleans the session; subsequent calls in the same request are
    no-ops.
    """
    for key in list(session):
        if key.startswith(_LEGACY_NUMBER_PREFIXES):
            del session[key]
    mix_modules = session.get("mix_modules")
    if isinstance(mix_modules, dict) and ("n20" in mix_modules or "n99" in mix_modules):
        session.pop("mix_modules", None)


def _check_kwargs(session: dict[str, Any]) -> dict[str, bool]:
    """Shared answer-check options derived from current session settings."""
    return {"diacritic_tolerant": _is_diacritic_tolerant(session)}


def _ui_lang(session: dict[str, Any]) -> str:
    return ui_lang_from_session(session)


def _t(session: dict[str, Any], english: str, lithuanian: str) -> str:
    return tr(_ui_lang(session), english, lithuanian)


def _render_page(
    session: dict[str, Any],
    *content: Any,
    active_module: str | None = None,
    current_path: str = "/",
) -> Any:
    lang = _ui_lang(session)
    return page_shell(
        *content,
        user_name=session.get("user_name"),
        active_module=active_module,
        lang=lang,
        diacritic_tolerant=_is_diacritic_tolerant(session),
        current_path=current_path,
    )


def _append_history_entry(
    session: dict[str, Any], history_key: str, entry: dict[str, Any]
) -> None:
    """Append one history entry and keep only the most recent N entries."""
    history = session.get(history_key)
    if not isinstance(history, list):
        history = []
    history.append(entry)
    session[history_key] = history[-_SESSION_HISTORY_LIMIT:]


def _build_answer_snapshot(
    question: str,
    user_answer: str,
    correct_answer: str,
    is_correct: bool,
    *,
    exercise_info: dict[str, Any] | None = None,
    row: dict[str, Any] | None = None,
    hour: int | None = None,
) -> dict[str, Any]:
    """Capture the answered exercise before the session mutates to the next one."""
    answer_text = user_answer.strip()
    correct_text = correct_answer.strip()
    diff_user, diff_correct = highlight_diff(answer_text, correct_text, is_correct)
    return {
        "question": question,
        "answer": answer_text,
        "correct": is_correct,
        "true_answer": correct_text,
        "diff_user": diff_user,
        "diff_correct": diff_correct,
        "exercise_info": exercise_info or {},
        "row": row,
        "hour": hour,
    }


def _history_entry_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Persist only the stable fields needed for exercise history."""
    return {
        "question": snapshot["question"],
        "answer": snapshot["answer"],
        "correct": snapshot["correct"],
        "true_answer": snapshot["true_answer"],
    }


def _append_snapshot_history(
    session: dict[str, Any], history_key: str, snapshot: dict[str, Any]
) -> None:
    _append_history_entry(session, history_key, _history_entry_from_snapshot(snapshot))


def _feedback_from_snapshot(snapshot: dict[str, Any], lang: str = "en") -> Any:
    """Build feedback from frozen answered state instead of live session keys."""
    exercise_info = snapshot.get("exercise_info", {})
    if snapshot["correct"]:
        return feedback_correct(
            snapshot["answer"],
            exercise_type=exercise_info.get("exercise_type"),
            grammatical_case=exercise_info.get("grammatical_case"),
            question=snapshot["question"],
            lang=lang,
        )

    fb_kwargs: dict[str, Any] = {
        "exercise_type": exercise_info.get("exercise_type"),
        "grammatical_case": exercise_info.get("grammatical_case"),
        "number_pattern": exercise_info.get("number_pattern"),
        "question": snapshot["question"],
        "lang": lang,
    }
    if snapshot.get("row") is not None:
        fb_kwargs["row"] = snapshot["row"]
    if snapshot.get("hour") is not None:
        fb_kwargs["hour"] = snapshot["hour"]
    return feedback_incorrect(
        snapshot["answer"],
        snapshot["true_answer"],
        snapshot["diff_user"],
        snapshot["diff_correct"],
        **fb_kwargs,
    )


def _ensure_session(session: dict[str, Any]) -> None:
    """Initialise defaults and generate first question if needed."""
    _strip_legacy_number_keys(session)
    session.setdefault("history", [])
    session.setdefault("correct_count", 0)
    session.setdefault("incorrect_count", 0)
    adaptive.init_tracking(session)
    if "current_question" not in session:
        _new_question(session)


def _new_question(session: dict[str, Any]) -> None:
    """Pick a new exercise and store it in the session."""
    ex = engine.generate(session)
    session["exercise_type"] = ex["exercise_type"]
    session["price"] = ex["price"]
    session["item"] = ex.get("item")
    session["row_id"] = ex["row"]["number"]
    session["number_pattern"] = ex.get(
        "number_pattern",
        number_pattern(ex["row"]["number"]),
    )
    session["grammatical_case"] = (
        "accusative" if ex["exercise_type"] == "kiek" else "nominative"
    )
    session["current_question"] = engine.format_question(
        ex["exercise_type"], ex["price"], ex.get("item")
    )


_MIX_Q_KEY_BY_MODULE = {
    "prices": "current_question",
    "time": "time_current_question",
    "numbers": "numbers_current_question",
    "age": "age_current_question",
    "weather": "weather_current_question",
}


def _refresh_cached_questions(session: dict[str, Any]) -> None:
    """Re-render cached *_current_question values in the current UI language.

    Preserves the in-progress exercise (row, type, etc.) but rewrites the
    prompt so a /set-language toggle updates what the user sees immediately.
    """
    from age_engine import PRONOUNS as _AGE_PRONOUNS

    lang = _ui_lang(session)

    if "current_question" in session and session.get("exercise_type"):
        session["current_question"] = engine.format_question(
            session["exercise_type"],
            session.get("price", ""),
            session.get("item"),
        )

    if "time_current_question" in session and session.get("time_display"):
        session["time_current_question"] = time_engine.format_question(
            session["time_display"]
        )

    for prefix, eng in (("numbers", number_engine),):
        qk = f"{prefix}_current_question"
        rid = session.get(f"{prefix}_row_id")
        ex_type = session.get(f"{prefix}_exercise_type")
        if qk in session and rid is not None and ex_type:
            row = next((r for r in eng.rows if r["number"] == rid), None)
            if row is not None:
                session[qk] = eng.format_question(ex_type, row, lang=lang)

    if "age_current_question" in session and session.get("age_row_id"):
        row = next((r for r in age_rows if r["number"] == session["age_row_id"]), None)
        dative = session.get("age_pronoun")
        ex_type = session.get("age_exercise_type")
        pronoun = next((p for p in _AGE_PRONOUNS if p["dative"] == dative), None)
        if row is not None and pronoun is not None and ex_type:
            session["age_current_question"] = age_engine.format_question(
                ex_type, row, pronoun, lang=lang
            )

    if "weather_current_question" in session and session.get("weather_row_id"):
        row = next(
            (r for r in weather_rows if r["number"] == session["weather_row_id"]),
            None,
        )
        ex_type = session.get("weather_exercise_type")
        if row is not None and ex_type:
            session["weather_current_question"] = weather_engine.format_question(
                ex_type, row, bool(session.get("weather_negative")), lang=lang
            )

    mix_mod = session.get("mix_current_module")
    if mix_mod in _MIX_Q_KEY_BY_MODULE and _MIX_Q_KEY_BY_MODULE[mix_mod] in session:
        session["mix_current_question"] = session[_MIX_Q_KEY_BY_MODULE[mix_mod]]


def _compute_module_stats(
    session: dict[str, Any],
    correct_key: str,
    incorrect_key: str,
    history_key: str,
    weak_areas_fn: Any,
) -> dict[str, Any]:
    """Compute stats for any module given its session key names."""
    corr = session.get(correct_key, 0)
    inc = session.get(incorrect_key, 0)
    tot = corr + inc
    streak = 0
    for entry in reversed(session.get(history_key, [])):
        if entry["correct"]:
            streak += 1
        else:
            break
    return {
        "total": tot,
        "correct": corr,
        "incorrect": inc,
        "accuracy": (corr / tot * 100) if tot else 0,
        "current_streak": streak,
        "weak_areas": weak_areas_fn(session),
    }


def _compute_stats(session: dict[str, Any]) -> dict[str, Any]:
    return _compute_module_stats(
        session, "correct_count", "incorrect_count", "history", adaptive.get_weak_areas
    )


def _compute_time_stats(session: dict[str, Any]) -> dict[str, Any]:
    return _compute_module_stats(
        session,
        "time_correct_count",
        "time_incorrect_count",
        "time_history",
        time_engine.get_weak_areas,
    )


# ------------------------------------------------------------------
# Time session helpers
# ------------------------------------------------------------------


def _ensure_time_session(session: dict[str, Any]) -> None:
    """Initialise time module defaults and generate first question if needed."""
    _strip_legacy_number_keys(session)
    session.setdefault("time_history", [])
    session.setdefault("time_correct_count", 0)
    session.setdefault("time_incorrect_count", 0)
    time_engine.init_tracking(session)
    if "time_current_question" not in session:
        _new_time_question(session)


def _new_time_question(session: dict[str, Any]) -> None:
    """Pick a new time exercise and store it in the session."""
    ex = time_engine.generate(session)
    session["time_exercise_type"] = ex["exercise_type"]
    session["time_hour"] = ex["hour"]
    session["time_minute"] = ex["minute"]
    session["time_display"] = ex["display_time"]
    session["time_number_pattern"] = ex["number_pattern"]
    session["time_grammatical_case"] = ex["grammatical_case"]
    session["time_current_question"] = time_engine.format_question(ex["display_time"])


# ------------------------------------------------------------------
# Number session helpers
# ------------------------------------------------------------------


def _ensure_number_session(
    session: dict[str, Any],
    engine_inst: NumberEngine,
    prefix: str,
    seed_prefix: str | None = None,
) -> None:
    """Initialise number module defaults and generate first question if needed."""
    _strip_legacy_number_keys(session)
    session.setdefault(f"{prefix}_history", [])
    session.setdefault(f"{prefix}_correct_count", 0)
    session.setdefault(f"{prefix}_incorrect_count", 0)
    engine_inst.init_tracking(session, prefix, seed_prefix=seed_prefix)
    if f"{prefix}_current_question" not in session:
        _new_number_question(session, engine_inst, prefix)


def _new_number_question(
    session: dict[str, Any], engine_inst: NumberEngine, prefix: str
) -> None:
    """Pick a new number exercise and store it in the session."""
    ex = engine_inst.generate(session, prefix)
    session[f"{prefix}_exercise_type"] = ex["exercise_type"]
    session[f"{prefix}_row_id"] = ex["row"]["number"]
    session[f"{prefix}_number_pattern"] = ex["number_pattern"]
    session[f"{prefix}_current_question"] = engine_inst.format_question(
        ex["exercise_type"], ex["row"], lang=_ui_lang(session)
    )


def _compute_number_stats(
    session: dict[str, Any], prefix: str, engine_inst: NumberEngine
) -> dict[str, Any]:
    return _compute_module_stats(
        session,
        f"{prefix}_correct_count",
        f"{prefix}_incorrect_count",
        f"{prefix}_history",
        lambda s: engine_inst.get_weak_areas(s, prefix),
    )


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------


@rt("/error")
def get_error(session) -> Any:
    return _render_page(
        session,
        Container(
            DivCentered(
                Span("🇱🇹", cls="text-6xl mb-4"),
                H2(
                    _t(session, "Something Went Wrong", "Ivyko Klaida"),
                    cls=(TextT.xl, TextT.bold),
                ),
                P(
                    _t(
                        session,
                        "Login failed. This usually happens if you cancel the Google sign-in.",
                        "Prisijungimas nepavyko. Taip dazniausiai nutinka atsaukus Google prisijungima.",
                    ),
                    cls=TextPresets.muted_lg,
                ),
                Div(
                    A(
                        UkIcon("rotate-ccw", cls="mr-2"),
                        _t(session, "Try Again", "Bandyti Dar Karta"),
                        href="/login",
                        cls="uk-btn uk-btn-primary",
                    ),
                    A(
                        UkIcon("arrow-left", cls="mr-2"),
                        _t(session, "Back to Home", "Atgal i Pradzia"),
                        href="/",
                        cls="uk-btn uk-btn-ghost ml-2",
                    ),
                    cls="mt-6 flex gap-2",
                ),
                cls="min-h-[40vh]",
            ),
            cls=(ContainerT.xl, "px-8 py-16"),
        ),
        current_path="/error",
    )


@rt("/login")
def get_login(req, session) -> Any:
    if session.get("auth"):
        return RedirectResponse("/", status_code=303)
    lang = _ui_lang(session)
    return _render_page(
        session,
        login_page_content(oauth.login_link(req), lang=lang),
        current_path="/login",
    )


@rt("/set-language")
def get_set_language(req, session, lang: str = "en") -> Any:
    session[UI_LANGUAGE_KEY] = normalize_ui_lang(lang)
    _refresh_cached_questions(session)
    if session.get("auth"):
        save_progress(session["auth"], session)
    referer = req.headers.get("referer", "/")
    from urllib.parse import urlparse

    parsed = urlparse(referer)
    redirect_to = parsed.path if parsed.path else "/"
    if parsed.query:
        redirect_to = f"{redirect_to}?{parsed.query}"
    if not redirect_to.startswith("/"):
        redirect_to = "/"
    return RedirectResponse(redirect_to, status_code=303)


@rt("/set-diacritic-mode")
def get_set_diacritic_mode(session, enabled: str = "0", next_path: str = "/") -> Any:
    session[_DIACRITIC_MODE_KEY] = enabled == "1"
    if session.get("auth"):
        save_progress(session["auth"], session)
    safe_next = (
        next_path if isinstance(next_path, str) and next_path.startswith("/") else "/"
    )
    return RedirectResponse(safe_next, status_code=303)


@rt("/")
def get_home(session) -> Any:
    lang = _ui_lang(session)
    return _render_page(
        session,
        landing_page_content(lang=lang),
        active_module="home",
        current_path="/",
    )


@rt("/prices")
def get_prices(session) -> Any:
    lang = _ui_lang(session)
    _ensure_session(session)
    stats = _compute_stats(session)
    history = session.get("history", [])

    reset_modal = Modal(
        ModalHeader(H3(_t(session, "Reset Progress?", "Atstatyti Pazanga?"))),
        ModalBody(
            P(
                _t(
                    session,
                    "This will clear all your history. Are you sure?",
                    "Bus isvalyta visa jusu istorija. Ar tikrai?",
                )
            )
        ),
        ModalFooter(
            Button(
                _t(session, "Cancel", "Atsaukti"),
                cls=ButtonT.ghost,
                data_uk_toggle="target: #reset-modal",
            ),
            Button(
                _t(session, "Reset", "Atstatyti"),
                cls=ButtonT.destructive,
                hx_post="/reset",
                hx_target="#quiz-area",
                hx_swap="outerHTML",
            ),
        ),
        id="reset-modal",
    )

    main_content = Container(
        H2(
            _t(session, "Lithuanian Price Practice", "Kalbejimo apie kainas praktika"),
            cls=(TextT.xl, "mb-2"),
        ),
        P(
            _t(
                session,
                "Practice expressing prices in Lithuanian. Type the full answer including the euro word.",
                "Mokykites kalbeti apie kainas. Irasykite pilna atsakyma su zodziu euras.",
            ),
            cls="text-base-content/70 text-sm mb-1",
        ),
        P(
            _t(session, "Two exercise types: ", "Du uzduociu tipai: "),
            Strong("Kokia kaina?"),
            _t(session, " (nominative) and ", " (vardininkas) ir "),
            Strong("Kiek kainuoja?"),
            _t(session, " (accusative).", " (galininkas)."),
            cls="text-base-content/60 text-xs mb-6",
        ),
        examples_section(lang=lang),
        quiz_area(
            session["current_question"],
            label=_t(session, "Prices", "Kainos"),
            lang=lang,
        ),
        Div(stats_panel(stats, history, lang=lang), cls="mt-6"),
        Button(
            UkIcon("refresh-ccw", cls="mr-2"),
            _t(session, "Reset Progress", "Atstatyti Pazanga"),
            cls=(ButtonT.destructive, "mt-6"),
            data_uk_toggle="target: #reset-modal",
        ),
        reset_modal,
        cls=(ContainerT.xl, "px-8 py-8"),
    )

    return _render_page(
        session,
        main_content,
        active_module="prices",
        current_path="/prices",
    )


@rt("/answer")
def post(session, user_answer: str = "") -> Any:
    lang = _ui_lang(session)
    _ensure_session(session)

    row = engine.get_row(session["row_id"])
    correct_answer = engine.correct_answer(session["exercise_type"], row)
    is_correct = engine.check(user_answer, correct_answer, **_check_kwargs(session))

    # Update counters
    if is_correct:
        session["correct_count"] = session.get("correct_count", 0) + 1
    else:
        session["incorrect_count"] = session.get("incorrect_count", 0) + 1

    # Update adaptive model
    exercise_info = {
        "exercise_type": session["exercise_type"],
        "number_pattern": session.get("number_pattern"),
        "grammatical_case": session.get("grammatical_case"),
    }
    snapshot = _build_answer_snapshot(
        session["current_question"],
        user_answer,
        correct_answer,
        is_correct,
        exercise_info=exercise_info,
        row=row,
    )
    _append_snapshot_history(session, "history", snapshot)
    adaptive.update(session, exercise_info, is_correct)

    # Pick next question
    _new_question(session)

    # Persist progress (only when logged in)
    if session.get("auth"):
        save_progress(session["auth"], session)

    # Build feedback
    fb = _feedback_from_snapshot(snapshot, lang=lang)

    # Return quiz area + OOB stats update
    stats = _compute_stats(session)
    oob_stats = stats_panel(stats, session.get("history", []), oob=True, lang=lang)

    return (
        quiz_area(
            session["current_question"],
            feedback=fb,
            label=_t(session, "Prices", "Kainos"),
            lang=lang,
        ),
        oob_stats,
    )


_PRICE_SESSION_KEYS = {
    "history",
    "correct_count",
    "incorrect_count",
    "performance",
    "current_question",
    "exercise_type",
    "price",
    "item",
    "row_id",
    "number_pattern",
    "grammatical_case",
}


@rt("/reset")
def post_reset(session) -> Any:
    lang = _ui_lang(session)
    for key in _PRICE_SESSION_KEYS & set(session.keys()):
        del session[key]

    _ensure_session(session)

    if session.get("auth"):
        save_progress(session["auth"], session)

    stats = _compute_stats(session)
    oob_stats = stats_panel(stats, [], oob=True, lang=lang)
    return (
        quiz_area(
            session["current_question"],
            label=_t(session, "Prices", "Kainos"),
            lang=lang,
        ),
        oob_stats,
    )


@rt("/stats")
def get_stats(session) -> Any:
    lang = _ui_lang(session)
    stats = _compute_stats(session)
    time_stats = _compute_time_stats(session)
    numbers_stats = _compute_number_stats(session, "numbers", number_engine)
    age_stats = _compute_age_stats(session)
    weather_stats = _compute_weather_stats(session)
    return _render_page(
        session,
        stats_page_content(
            stats,
            session,
            time_stats=time_stats,
            numbers_stats=numbers_stats,
            age_stats=age_stats,
            weather_stats=weather_stats,
            lang=lang,
        ),
        current_path="/stats",
    )


@rt("/about")
def get_about(session) -> Any:
    lang = _ui_lang(session)
    return _render_page(session, about_page_content(lang=lang), current_path="/about")


# ------------------------------------------------------------------
# Time routes
# ------------------------------------------------------------------


@rt("/time")
def get_time(session) -> Any:
    lang = _ui_lang(session)
    _ensure_time_session(session)
    stats = _compute_time_stats(session)
    history = session.get("time_history", [])

    reset_modal = Modal(
        ModalHeader(H3(_t(session, "Reset Progress?", "Atstatyti Pazanga?"))),
        ModalBody(
            P(
                _t(
                    session,
                    "This will clear all your time practice history. Are you sure?",
                    "Bus isvalyta visa laiko praktikos istorija. Ar tikrai?",
                )
            )
        ),
        ModalFooter(
            Button(
                _t(session, "Cancel", "Atsaukti"),
                cls=ButtonT.ghost,
                data_uk_toggle="target: #reset-modal",
            ),
            Button(
                _t(session, "Reset", "Atstatyti"),
                cls=ButtonT.destructive,
                hx_post="/time/reset",
                hx_target="#quiz-area",
                hx_swap="outerHTML",
            ),
        ),
        id="reset-modal",
    )

    main_content = Container(
        H2(
            _t(session, "Lithuanian Time Practice", "Kalbejimo apie laika praktika"),
            cls=(TextT.xl, "mb-2"),
        ),
        P(
            _t(
                session,
                "Practice expressing time in Lithuanian. Type the full answer.",
                "Mokykites kalbeti apie laika. Irasykite pilna atsakyma.",
            ),
            cls="text-base-content/70 text-sm mb-1",
        ),
        P(
            _t(session, "Four exercise types: ", "Keturi uzduociu tipai: "),
            Strong(_t(session, "whole hours", "pilnos valandos")),
            ", ",
            Strong(_t(session, "half past", "puse")),
            ", ",
            Strong(_t(session, "quarter past", "penkiolika minuciu po")),
            ", and ",
            Strong(_t(session, "quarter to", "be penkiolikos minuciu")),
            ".",
            cls="text-base-content/60 text-xs mb-6",
        ),
        time_examples_section(lang=lang),
        quiz_area(
            session["time_current_question"],
            post_url="/time/answer",
            label=_t(session, "Time", "Laikas"),
            lang=lang,
        ),
        Div(stats_panel(stats, history, lang=lang), cls="mt-6"),
        Button(
            UkIcon("refresh-ccw", cls="mr-2"),
            _t(session, "Reset Progress", "Atstatyti Pazanga"),
            cls=(ButtonT.destructive, "mt-6"),
            data_uk_toggle="target: #reset-modal",
        ),
        reset_modal,
        cls=(ContainerT.xl, "px-8 py-8"),
    )

    return _render_page(
        session,
        main_content,
        active_module="time",
        current_path="/time",
    )


@rt("/time/answer")
def post_time_answer(session, user_answer: str = "") -> Any:
    lang = _ui_lang(session)
    _ensure_time_session(session)

    correct_answer = time_engine.correct_answer(
        session["time_exercise_type"],
        session["time_hour"],
        session["time_minute"],
    )
    is_correct = time_engine.check(
        user_answer, correct_answer, **_check_kwargs(session)
    )

    if is_correct:
        session["time_correct_count"] = session.get("time_correct_count", 0) + 1
    else:
        session["time_incorrect_count"] = session.get("time_incorrect_count", 0) + 1

    exercise_info = {
        "exercise_type": session["time_exercise_type"],
        "number_pattern": session.get("time_number_pattern"),
        "grammatical_case": session.get("time_grammatical_case"),
    }
    snapshot = _build_answer_snapshot(
        session["time_current_question"],
        user_answer,
        correct_answer,
        is_correct,
        exercise_info=exercise_info,
        hour=session["time_hour"],
    )
    _append_snapshot_history(session, "time_history", snapshot)
    time_engine.update(session, exercise_info, is_correct)

    _new_time_question(session)

    # Persist progress (only when logged in)
    if session.get("auth"):
        save_progress(session["auth"], session)

    fb = _feedback_from_snapshot(snapshot, lang=lang)

    stats = _compute_time_stats(session)
    oob_stats = stats_panel(stats, session.get("time_history", []), oob=True, lang=lang)

    return (
        quiz_area(
            session["time_current_question"],
            feedback=fb,
            post_url="/time/answer",
            label=_t(session, "Time", "Laikas"),
            lang=lang,
        ),
        oob_stats,
    )


@rt("/time/reset")
def post_time_reset(session) -> Any:
    lang = _ui_lang(session)
    for key in [k for k in list(session.keys()) if k.startswith("time_")]:
        del session[key]

    _ensure_time_session(session)

    if session.get("auth"):
        save_progress(session["auth"], session)

    stats = _compute_time_stats(session)
    oob_stats = stats_panel(stats, [], oob=True, lang=lang)
    return (
        quiz_area(
            session["time_current_question"],
            post_url="/time/answer",
            label=_t(session, "Time", "Laikas"),
            lang=lang,
        ),
        oob_stats,
    )


# ------------------------------------------------------------------
# Age session helpers
# ------------------------------------------------------------------


def _ensure_age_session(session: dict[str, Any]) -> None:
    """Initialise age module defaults and generate first question if needed."""
    _strip_legacy_number_keys(session)
    session.setdefault("age_history", [])
    session.setdefault("age_correct_count", 0)
    session.setdefault("age_incorrect_count", 0)
    age_engine.init_tracking(session, "age", seed_prefix="numbers")
    if "age_current_question" not in session:
        _new_age_question(session)


def _new_age_question(session: dict[str, Any]) -> None:
    """Pick a new age exercise and store it in the session."""
    ex = age_engine.generate(session, "age")
    session["age_exercise_type"] = ex["exercise_type"]
    session["age_row_id"] = ex["row"]["number"]
    session["age_number_pattern"] = ex["number_pattern"]
    session["age_pronoun"] = ex["pronoun"]["dative"]
    session["age_current_question"] = age_engine.format_question(
        ex["exercise_type"], ex["row"], ex["pronoun"], lang=_ui_lang(session)
    )


def _compute_age_stats(session: dict[str, Any]) -> dict[str, Any]:
    return _compute_module_stats(
        session,
        "age_correct_count",
        "age_incorrect_count",
        "age_history",
        lambda s: age_engine.get_weak_areas(s, "age"),
    )


# ------------------------------------------------------------------
# Weather session helpers
# ------------------------------------------------------------------


def _ensure_weather_session(session: dict[str, Any]) -> None:
    """Initialise weather module defaults and generate first question if needed."""
    _strip_legacy_number_keys(session)
    session.setdefault("weather_history", [])
    session.setdefault("weather_correct_count", 0)
    session.setdefault("weather_incorrect_count", 0)
    weather_engine.init_tracking(session, "weather", seed_prefix="numbers")
    if "weather_current_question" not in session:
        _new_weather_question(session)


def _new_weather_question(session: dict[str, Any]) -> None:
    """Pick a new weather exercise and store it in the session."""
    ex = weather_engine.generate(session, "weather")
    session["weather_exercise_type"] = ex["exercise_type"]
    session["weather_row_id"] = ex["row"]["number"]
    session["weather_number_pattern"] = ex["number_pattern"]
    session["weather_negative"] = ex["negative"]
    session["weather_current_question"] = weather_engine.format_question(
        ex["exercise_type"], ex["row"], ex["negative"], lang=_ui_lang(session)
    )


def _compute_weather_stats(session: dict[str, Any]) -> dict[str, Any]:
    return _compute_module_stats(
        session,
        "weather_correct_count",
        "weather_incorrect_count",
        "weather_history",
        lambda s: weather_engine.get_weak_areas(s, "weather"),
    )


# ------------------------------------------------------------------
# Age routes
# ------------------------------------------------------------------


@rt("/age")
def get_age(session) -> Any:
    lang = _ui_lang(session)
    _ensure_age_session(session)
    stats = _compute_age_stats(session)
    history = session.get("age_history", [])

    reset_modal = Modal(
        ModalHeader(H3(_t(session, "Reset Progress?", "Atstatyti Pazanga?"))),
        ModalBody(
            P(
                _t(
                    session,
                    "This will clear all your age practice history. Are you sure?",
                    "Bus isvalyta visa amziaus praktikos istorija. Ar tikrai?",
                )
            )
        ),
        ModalFooter(
            Button(
                _t(session, "Cancel", "Atsaukti"),
                cls=ButtonT.ghost,
                data_uk_toggle="target: #reset-modal",
            ),
            Button(
                _t(session, "Reset", "Atstatyti"),
                cls=ButtonT.destructive,
                hx_post="/age/reset",
                hx_target="#quiz-area",
                hx_swap="outerHTML",
            ),
        ),
        id="reset-modal",
    )

    main_content = Container(
        H2(
            _t(session, "Lithuanian Age Practice", "Kalbejimo apie amziu praktika"),
            cls=(TextT.xl, "mb-2"),
        ),
        P(
            _t(
                session,
                "Practice expressing ages in Lithuanian with dative pronouns.",
                "Mokykites kalbeti apie amziu parinkdami tinkama ivardi ir linksni.",
            ),
            cls="text-base-content/70 text-sm mb-1",
        ),
        P(
            _t(session, "Two exercise types: ", "Du uzduociu tipai: "),
            Strong(_t(session, "produce", "kurimas")),
            _t(
                session,
                " (say the age in Lithuanian) and ",
                " (pasakykite amziu lietuviskai) ir ",
            ),
            Strong(_t(session, "recognize", "atpazinimas")),
            _t(
                session,
                " (identify the age from Lithuanian).",
                " (atpazinkite amziu is lietuviskos frazes).",
            ),
            cls="text-base-content/60 text-xs mb-6",
        ),
        age_examples_section(lang=lang),
        quiz_area(
            session["age_current_question"],
            post_url="/age/answer",
            label=_t(session, "Age", "Amzius"),
            lang=lang,
        ),
        Div(stats_panel(stats, history, lang=lang), cls="mt-6"),
        Button(
            UkIcon("refresh-ccw", cls="mr-2"),
            _t(session, "Reset Progress", "Atstatyti Pazanga"),
            cls=(ButtonT.destructive, "mt-6"),
            data_uk_toggle="target: #reset-modal",
        ),
        reset_modal,
        cls=(ContainerT.xl, "px-8 py-8"),
    )

    return _render_page(
        session,
        main_content,
        active_module="age",
        current_path="/age",
    )


@rt("/age/answer")
def post_age_answer(session, user_answer: str = "") -> Any:
    lang = _ui_lang(session)
    _ensure_age_session(session)

    row_id = session["age_row_id"]
    ex_type = session["age_exercise_type"]
    pronoun_dative = session["age_pronoun"]

    row = age_rows[0]  # fallback
    for r in age_rows:
        if r["number"] == row_id:
            row = r
            break

    from age_engine import _pronoun_by_dative

    pronoun = _pronoun_by_dative(pronoun_dative)
    correct = age_engine.correct_answer(ex_type, row, pronoun)
    is_correct = age_engine.check(
        user_answer, correct, ex_type, **_check_kwargs(session)
    )

    if is_correct:
        session["age_correct_count"] = session.get("age_correct_count", 0) + 1
    else:
        session["age_incorrect_count"] = session.get("age_incorrect_count", 0) + 1

    exercise_info = {
        "exercise_type": ex_type,
        "number_pattern": session.get("age_number_pattern"),
        "pronoun": pronoun_dative,
    }
    snapshot = _build_answer_snapshot(
        session["age_current_question"],
        user_answer,
        correct,
        is_correct,
        exercise_info=exercise_info,
    )
    _append_snapshot_history(session, "age_history", snapshot)
    age_engine.update(session, "age", exercise_info, is_correct)

    _new_age_question(session)

    if session.get("auth"):
        save_progress(session["auth"], session)

    fb = _feedback_from_snapshot(snapshot, lang=lang)

    stats = _compute_age_stats(session)
    oob_stats = stats_panel(stats, session.get("age_history", []), oob=True, lang=lang)

    return (
        quiz_area(
            session["age_current_question"],
            feedback=fb,
            post_url="/age/answer",
            label=_t(session, "Age", "Amzius"),
            lang=lang,
        ),
        oob_stats,
    )


@rt("/age/reset")
def post_age_reset(session) -> Any:
    lang = _ui_lang(session)
    for key in [k for k in list(session.keys()) if k.startswith("age_")]:
        del session[key]

    _ensure_age_session(session)

    if session.get("auth"):
        save_progress(session["auth"], session)

    stats = _compute_age_stats(session)
    oob_stats = stats_panel(stats, [], oob=True, lang=lang)
    return (
        quiz_area(
            session["age_current_question"],
            post_url="/age/answer",
            label=_t(session, "Age", "Amzius"),
            lang=lang,
        ),
        oob_stats,
    )


# ------------------------------------------------------------------
# Weather routes
# ------------------------------------------------------------------


@rt("/weather")
def get_weather(session) -> Any:
    lang = _ui_lang(session)
    _ensure_weather_session(session)
    stats = _compute_weather_stats(session)
    history = session.get("weather_history", [])

    reset_modal = Modal(
        ModalHeader(H3(_t(session, "Reset Progress?", "Atstatyti Pazanga?"))),
        ModalBody(
            P(
                _t(
                    session,
                    "This will clear all your weather practice history. Are you sure?",
                    "Bus isvalyta visa oro praktikos istorija. Ar tikrai?",
                )
            )
        ),
        ModalFooter(
            Button(
                _t(session, "Cancel", "Atsaukti"),
                cls=ButtonT.ghost,
                data_uk_toggle="target: #reset-modal",
            ),
            Button(
                _t(session, "Reset", "Atstatyti"),
                cls=ButtonT.destructive,
                hx_post="/weather/reset",
                hx_target="#quiz-area",
                hx_swap="outerHTML",
            ),
        ),
        id="reset-modal",
    )

    main_content = Container(
        H2(
            _t(session, "Lithuanian Weather Practice", "Kalbejimas apie ora"),
            cls=(TextT.xl, "mb-2"),
        ),
        P(
            _t(
                session,
                "Practice expressing temperatures in Lithuanian.",
                "Kalbejimo apie temperatura praktika.",
            ),
            cls="text-base-content/70 text-sm mb-1",
        ),
        P(
            _t(session, "Two exercise types: ", "Du uzduociu tipai: "),
            Strong(_t(session, "produce", "kurimas")),
            _t(
                session,
                " (say the temperature in Lithuanian) and ",
                " (pasakykite temperatura lietuviskai) ir ",
            ),
            Strong(_t(session, "recognize", "atpazinimas")),
            _t(
                session,
                " (identify the temperature from Lithuanian).",
                " (atpazinkite temperatura is lietuviskos frazes).",
            ),
            cls="text-base-content/60 text-xs mb-6",
        ),
        weather_examples_section(lang=lang),
        quiz_area(
            session["weather_current_question"],
            post_url="/weather/answer",
            label=_t(session, "Weather", "Oras"),
            lang=lang,
        ),
        Div(stats_panel(stats, history, lang=lang), cls="mt-6"),
        Button(
            UkIcon("refresh-ccw", cls="mr-2"),
            _t(session, "Reset Progress", "Atstatyti Pazanga"),
            cls=(ButtonT.destructive, "mt-6"),
            data_uk_toggle="target: #reset-modal",
        ),
        reset_modal,
        cls=(ContainerT.xl, "px-8 py-8"),
    )

    return _render_page(
        session,
        main_content,
        active_module="weather",
        current_path="/weather",
    )


@rt("/weather/answer")
def post_weather_answer(session, user_answer: str = "") -> Any:
    lang = _ui_lang(session)
    _ensure_weather_session(session)

    row_id = session["weather_row_id"]
    ex_type = session["weather_exercise_type"]
    negative = session["weather_negative"]

    row = weather_rows[0]  # fallback
    for r in weather_rows:
        if r["number"] == row_id:
            row = r
            break

    correct = weather_engine.correct_answer(ex_type, row, negative)
    is_correct = weather_engine.check(
        user_answer, correct, ex_type, **_check_kwargs(session)
    )

    if is_correct:
        session["weather_correct_count"] = session.get("weather_correct_count", 0) + 1
    else:
        session["weather_incorrect_count"] = (
            session.get("weather_incorrect_count", 0) + 1
        )

    exercise_info = {
        "exercise_type": ex_type,
        "number_pattern": session.get("weather_number_pattern"),
        "sign": "negative" if negative else "positive",
    }
    snapshot = _build_answer_snapshot(
        session["weather_current_question"],
        user_answer,
        correct,
        is_correct,
        exercise_info=exercise_info,
    )
    _append_snapshot_history(session, "weather_history", snapshot)
    weather_engine.update(session, "weather", exercise_info, is_correct)

    _new_weather_question(session)

    if session.get("auth"):
        save_progress(session["auth"], session)

    fb = _feedback_from_snapshot(snapshot, lang=lang)

    stats = _compute_weather_stats(session)
    oob_stats = stats_panel(
        stats, session.get("weather_history", []), oob=True, lang=lang
    )

    return (
        quiz_area(
            session["weather_current_question"],
            feedback=fb,
            post_url="/weather/answer",
            label=_t(session, "Weather", "Oras"),
            lang=lang,
        ),
        oob_stats,
    )


@rt("/weather/reset")
def post_weather_reset(session) -> Any:
    lang = _ui_lang(session)
    for key in [k for k in list(session.keys()) if k.startswith("weather_")]:
        del session[key]

    _ensure_weather_session(session)

    if session.get("auth"):
        save_progress(session["auth"], session)

    stats = _compute_weather_stats(session)
    oob_stats = stats_panel(stats, [], oob=True, lang=lang)
    return (
        quiz_area(
            session["weather_current_question"],
            post_url="/weather/answer",
            label=_t(session, "Weather", "Oras"),
            lang=lang,
        ),
        oob_stats,
    )


# ------------------------------------------------------------------
# Number routes (shared logic, parameterized by engine + prefix)
# ------------------------------------------------------------------


def _make_number_routes(
    engine_inst: NumberEngine,
    prefix: str,
    route_base: str,
    module_name: str,
    seed_prefix: str | None = None,
) -> None:
    """Register GET/POST routes for a number module."""

    @rt(route_base)
    def get_numbers(session) -> Any:
        lang = _ui_lang(session)
        _ensure_number_session(session, engine_inst, prefix, seed_prefix=seed_prefix)
        stats = _compute_number_stats(session, prefix, engine_inst)
        history = session.get(f"{prefix}_history", [])
        title_text = _t(session, "Lithuanian Numbers", "Skaičiai")
        subtitle_text = _t(
            session,
            "Lithuanian number words from 0 to 99.",
            "Skaičių žodžiai nuo 0 iki 99.",
        )

        reset_modal = Modal(
            ModalHeader(H3(_t(session, "Reset Progress?", "Atstatyti Pazanga?"))),
            ModalBody(
                P(
                    _t(
                        session,
                        "This will clear all your number practice history. Are you sure?",
                        "Bus isvalyta visa skaiciu praktikos istorija. Ar tikrai?",
                    )
                )
            ),
            ModalFooter(
                Button(
                    _t(session, "Cancel", "Atsaukti"),
                    cls=ButtonT.ghost,
                    data_uk_toggle="target: #reset-modal",
                ),
                Button(
                    _t(session, "Reset", "Atstatyti"),
                    cls=ButtonT.destructive,
                    hx_post=f"{route_base}/reset",
                    hx_target="#quiz-area",
                    hx_swap="outerHTML",
                ),
            ),
            id="reset-modal",
        )

        main_content = Container(
            H2(title_text, cls=(TextT.xl, "mb-2")),
            P(
                subtitle_text,
                cls="text-base-content/70 text-sm mb-1",
            ),
            P(
                _t(session, "Two exercise types: ", "Du uzduociu tipai: "),
                Strong(_t(session, "produce", "kurimas")),
                _t(
                    session,
                    " (say the number in Lithuanian) and ",
                    " (pasakykite skaiciu lietuviskai) ir ",
                ),
                Strong(_t(session, "recognize", "atpazinimas")),
                _t(
                    session,
                    " (identify the number from Lithuanian).",
                    " (atpazinkite skaiciu is lietuviskos israiskos).",
                ),
                cls="text-base-content/60 text-xs mb-6",
            ),
            number_examples_section(lang=lang),
            quiz_area(
                session[f"{prefix}_current_question"],
                post_url=f"{route_base}/answer",
                label=_t(session, "Numbers", "Skaiciai"),
                lang=lang,
            ),
            Div(stats_panel(stats, history, lang=lang), cls="mt-6"),
            Button(
                UkIcon("refresh-ccw", cls="mr-2"),
                _t(session, "Reset Progress", "Atstatyti Pazanga"),
                cls=(ButtonT.destructive, "mt-6"),
                data_uk_toggle="target: #reset-modal",
            ),
            reset_modal,
            cls=(ContainerT.xl, "px-8 py-8"),
        )

        return _render_page(
            session,
            main_content,
            active_module=module_name,
            current_path=route_base,
        )

    @rt(f"{route_base}/answer")
    def post_number_answer(session, user_answer: str = "") -> Any:
        lang = _ui_lang(session)
        _ensure_number_session(session, engine_inst, prefix, seed_prefix=seed_prefix)

        row_id = session[f"{prefix}_row_id"]
        ex_type = session[f"{prefix}_exercise_type"]
        row = engine_inst.rows[0]  # fallback
        for r in engine_inst.rows:
            if r["number"] == row_id:
                row = r
                break

        correct = engine_inst.correct_answer(ex_type, row)
        is_correct = engine_inst.check(
            user_answer, correct, ex_type, **_check_kwargs(session)
        )

        if is_correct:
            session[f"{prefix}_correct_count"] = (
                session.get(f"{prefix}_correct_count", 0) + 1
            )
        else:
            session[f"{prefix}_incorrect_count"] = (
                session.get(f"{prefix}_incorrect_count", 0) + 1
            )

        exercise_info = {
            "exercise_type": ex_type,
            "number_pattern": session.get(f"{prefix}_number_pattern"),
        }
        snapshot = _build_answer_snapshot(
            session[f"{prefix}_current_question"],
            user_answer,
            correct,
            is_correct,
            exercise_info=exercise_info,
        )
        _append_snapshot_history(session, f"{prefix}_history", snapshot)
        engine_inst.update(session, prefix, exercise_info, is_correct)

        _new_number_question(session, engine_inst, prefix)

        if session.get("auth"):
            save_progress(session["auth"], session)

        fb = _feedback_from_snapshot(snapshot, lang=lang)

        stats = _compute_number_stats(session, prefix, engine_inst)
        oob_stats = stats_panel(
            stats, session.get(f"{prefix}_history", []), oob=True, lang=lang
        )

        return (
            quiz_area(
                session[f"{prefix}_current_question"],
                feedback=fb,
                post_url=f"{route_base}/answer",
                label=_t(session, "Numbers", "Skaiciai"),
                lang=lang,
            ),
            oob_stats,
        )

    @rt(f"{route_base}/reset")
    def post_number_reset(session) -> Any:
        lang = _ui_lang(session)
        for key in [k for k in list(session.keys()) if k.startswith(f"{prefix}_")]:
            del session[key]

        _ensure_number_session(session, engine_inst, prefix, seed_prefix=seed_prefix)

        if session.get("auth"):
            save_progress(session["auth"], session)

        stats = _compute_number_stats(session, prefix, engine_inst)
        oob_stats = stats_panel(stats, [], oob=True, lang=lang)
        return (
            quiz_area(
                session[f"{prefix}_current_question"],
                post_url=f"{route_base}/answer",
                label=_t(session, "Numbers", "Skaiciai"),
                lang=lang,
            ),
            oob_stats,
        )


_make_number_routes(
    number_engine,
    "numbers",
    "/numbers",
    "numbers",
)


@rt("/numbers-20")
@rt("/numbers-99")
def get_legacy_numbers() -> Any:
    return RedirectResponse("/numbers", status_code=301)


# ------------------------------------------------------------------
# Practice All (mix) helpers
# ------------------------------------------------------------------

_MIX_MODULES = {
    "numbers": {
        "ensure": lambda s: _ensure_number_session(s, number_engine, "numbers"),
        "new_q": lambda s: _new_number_question(s, number_engine, "numbers"),
        "label": "Numbers",
    },
    "age": {
        "ensure": _ensure_age_session,
        "new_q": _new_age_question,
        "label": "Age",
    },
    "weather": {
        "ensure": _ensure_weather_session,
        "new_q": _new_weather_question,
        "label": "Weather",
    },
    "prices": {
        "ensure": _ensure_session,
        "new_q": _new_question,
        "label": "Prices",
    },
    "time": {
        "ensure": _ensure_time_session,
        "new_q": _new_time_question,
        "label": "Time",
    },
}

_MIX_TRANSIENT_KEYS: dict[str, tuple[str, ...]] = {
    "numbers": (
        "numbers_exercise_type",
        "numbers_row_id",
        "numbers_number_pattern",
        "numbers_current_question",
    ),
    "age": (
        "age_exercise_type",
        "age_row_id",
        "age_number_pattern",
        "age_pronoun",
        "age_current_question",
    ),
    "weather": (
        "weather_exercise_type",
        "weather_row_id",
        "weather_number_pattern",
        "weather_negative",
        "weather_current_question",
    ),
    "prices": (
        "exercise_type",
        "price",
        "item",
        "row_id",
        "number_pattern",
        "grammatical_case",
        "current_question",
    ),
    "time": (
        "time_exercise_type",
        "time_hour",
        "time_minute",
        "time_display",
        "time_number_pattern",
        "time_grammatical_case",
        "time_current_question",
    ),
}


def _clear_mix_transient_state(session: dict[str, Any], keep_module: str) -> None:
    """Drop stale per-module question keys not needed for the next mix step."""
    for mod, keys in _MIX_TRANSIENT_KEYS.items():
        if mod == keep_module:
            continue
        for key in keys:
            session.pop(key, None)


def _mix_module_label(session: dict[str, Any], module_name: str) -> str:
    labels = {
        "numbers": ("Numbers", "Skaičiai"),
        "age": ("Age", "Amzius"),
        "weather": ("Weather", "Oras"),
        "prices": ("Prices", "Kainos"),
        "time": ("Time", "Laikas"),
    }
    en, lt = labels.get(module_name, (module_name, module_name))
    return _t(session, en, lt)


def _ensure_mix_session(session: dict[str, Any]) -> None:
    """Initialise practice-all session and all sub-module sessions."""
    _strip_legacy_number_keys(session)
    session.setdefault("mix_history", [])
    session.setdefault("mix_correct_count", 0)
    session.setdefault("mix_incorrect_count", 0)
    session.setdefault(
        "mix_modules",
        {m: {"correct": 0, "incorrect": 1} for m in _MIX_MODULES},
    )
    if "mix_current_question" not in session:
        _new_mix_question(session)


def _new_mix_question(session: dict[str, Any]) -> None:
    """Thompson-sample a module, generate a question from it."""
    import random

    if random.random() < 0.2:
        mod_name = random.choice(list(_MIX_MODULES))
    else:
        mod_name = _sample_weakest(session["mix_modules"])

    q_key = {
        "numbers": "numbers_current_question",
        "age": "age_current_question",
        "weather": "weather_current_question",
        "prices": "current_question",
        "time": "time_current_question",
    }[mod_name]
    _clear_mix_transient_state(session, keep_module=mod_name)
    _MIX_MODULES[mod_name]["new_q"](session)
    session["mix_current_module"] = mod_name

    # Copy the question text from the sub-module's session key
    session["mix_current_question"] = session[q_key]


def _compute_mix_stats(session: dict[str, Any]) -> dict[str, Any]:
    return _compute_module_stats(
        session,
        "mix_correct_count",
        "mix_incorrect_count",
        "mix_history",
        lambda s: {},  # no weak-area breakdown for mix mode
    )


def _check_mix_answer(
    session: dict[str, Any], user_answer: str
) -> tuple[bool, str, dict[str, Any], dict[str, Any] | None]:
    """Dispatch answer check to the correct module engine.

    Returns (is_correct, correct_answer, exercise_info, row_or_none).
    """
    mod = session["mix_current_module"]
    check_kwargs = _check_kwargs(session)

    if mod == "numbers":
        prefix = mod
        eng = number_engine
        row_id = session[f"{prefix}_row_id"]
        ex_type = session[f"{prefix}_exercise_type"]
        row = next((r for r in eng.rows if r["number"] == row_id), eng.rows[0])
        correct = eng.correct_answer(ex_type, row)
        is_correct = eng.check(user_answer, correct, ex_type, **check_kwargs)
        exercise_info = {
            "exercise_type": ex_type,
            "number_pattern": session.get(f"{prefix}_number_pattern"),
        }
        eng.update(session, prefix, exercise_info, is_correct)
        return is_correct, correct, exercise_info, row

    if mod == "age":
        from age_engine import _pronoun_by_dative

        row_id = session["age_row_id"]
        ex_type = session["age_exercise_type"]
        pronoun_dative = session["age_pronoun"]
        row = next((r for r in age_rows if r["number"] == row_id), age_rows[0])
        pronoun = _pronoun_by_dative(pronoun_dative)
        correct = age_engine.correct_answer(ex_type, row, pronoun)
        is_correct = age_engine.check(user_answer, correct, ex_type, **check_kwargs)
        exercise_info = {
            "exercise_type": ex_type,
            "number_pattern": session.get("age_number_pattern"),
            "pronoun": pronoun_dative,
        }
        age_engine.update(session, "age", exercise_info, is_correct)
        return is_correct, correct, exercise_info, row

    if mod == "weather":
        row_id = session["weather_row_id"]
        ex_type = session["weather_exercise_type"]
        negative = session["weather_negative"]
        row = next((r for r in weather_rows if r["number"] == row_id), weather_rows[0])
        correct = weather_engine.correct_answer(ex_type, row, negative)
        is_correct = weather_engine.check(user_answer, correct, ex_type, **check_kwargs)
        exercise_info = {
            "exercise_type": ex_type,
            "number_pattern": session.get("weather_number_pattern"),
            "sign": "negative" if negative else "positive",
        }
        weather_engine.update(session, "weather", exercise_info, is_correct)
        return is_correct, correct, exercise_info, row

    if mod == "prices":
        row = engine.get_row(session["row_id"])
        correct = engine.correct_answer(session["exercise_type"], row)
        is_correct = engine.check(user_answer, correct, **check_kwargs)
        exercise_info = {
            "exercise_type": session["exercise_type"],
            "number_pattern": session.get("number_pattern"),
            "grammatical_case": session.get("grammatical_case"),
        }
        adaptive.update(session, exercise_info, is_correct)
        return is_correct, correct, exercise_info, row

    # time
    ex_type = session["time_exercise_type"]
    correct = time_engine.correct_answer(
        ex_type, session["time_hour"], session["time_minute"]
    )
    is_correct = time_engine.check(user_answer, correct, **check_kwargs)
    exercise_info = {
        "exercise_type": ex_type,
        "number_pattern": session.get("time_number_pattern"),
        "grammatical_case": session.get("time_grammatical_case"),
    }
    time_engine.update(session, exercise_info, is_correct)
    return is_correct, correct, exercise_info, None


# ------------------------------------------------------------------
# Practice All routes
# ------------------------------------------------------------------


@rt("/practice-all")
def get_practice_all(session) -> Any:
    lang = _ui_lang(session)
    _ensure_mix_session(session)
    stats = _compute_mix_stats(session)
    history = session.get("mix_history", [])
    mod = session.get("mix_current_module", "numbers")
    label = _mix_module_label(session, mod)

    reset_modal = Modal(
        ModalHeader(H3(_t(session, "Reset Progress?", "Atstatyti Pazanga?"))),
        ModalBody(
            P(
                _t(
                    session,
                    "This will clear your Practice All history. Are you sure?",
                    "Bus isvalyta Bendra Praktika istorija. Ar tikrai?",
                )
            )
        ),
        ModalFooter(
            Button(
                _t(session, "Cancel", "Atsaukti"),
                cls=ButtonT.ghost,
                data_uk_toggle="target: #reset-modal",
            ),
            Button(
                _t(session, "Reset", "Atstatyti"),
                cls=ButtonT.destructive,
                hx_post="/practice-all/reset",
                hx_target="#quiz-area",
                hx_swap="outerHTML",
            ),
        ),
        id="reset-modal",
    )

    main_content = Container(
        H2(_t(session, "Practice All", "Bendra Praktika"), cls=(TextT.xl, "mb-2")),
        P(
            _t(
                session,
                "Random exercises from all modules, weighted toward your weak spots.",
                "Atsitiktines uzduotys is visu moduliu, daugiau demesio silpniausioms vietoms.",
            ),
            cls="text-base-content/70 text-sm mb-6",
        ),
        quiz_area(
            session["mix_current_question"],
            post_url="/practice-all/answer",
            label=label,
            lang=lang,
        ),
        Div(stats_panel(stats, history, lang=lang), cls="mt-6"),
        Button(
            UkIcon("refresh-ccw", cls="mr-2"),
            _t(session, "Reset Progress", "Atstatyti Pazanga"),
            cls=(ButtonT.destructive, "mt-6"),
            data_uk_toggle="target: #reset-modal",
        ),
        reset_modal,
        cls=(ContainerT.xl, "px-8 py-8"),
    )

    return _render_page(
        session,
        main_content,
        active_module="practice-all",
        current_path="/practice-all",
    )


@rt("/practice-all/answer")
def post_practice_all_answer(session, user_answer: str = "") -> Any:
    lang = _ui_lang(session)
    _ensure_mix_session(session)

    is_correct, correct_answer, exercise_info, row = _check_mix_answer(
        session, user_answer
    )
    answered_module = session["mix_current_module"]
    answered_hour = session.get("time_hour") if answered_module == "time" else None

    # Update mix-level counters
    if is_correct:
        session["mix_correct_count"] = session.get("mix_correct_count", 0) + 1
    else:
        session["mix_incorrect_count"] = session.get("mix_incorrect_count", 0) + 1

    # Update mix-level Thompson Sampling
    from thompson import bump as _bump

    _bump(session["mix_modules"], answered_module, is_correct)

    snapshot = _build_answer_snapshot(
        session["mix_current_question"],
        user_answer,
        correct_answer,
        is_correct,
        exercise_info=exercise_info,
        row=row,
        hour=answered_hour,
    )
    _append_snapshot_history(session, "mix_history", snapshot)

    # Pick next question
    _new_mix_question(session)

    if session.get("auth"):
        save_progress(session["auth"], session)

    # Feedback
    fb = _feedback_from_snapshot(snapshot, lang=lang)

    new_mod = session["mix_current_module"]
    new_label = _mix_module_label(session, new_mod)

    stats = _compute_mix_stats(session)
    oob_stats = stats_panel(stats, session.get("mix_history", []), oob=True, lang=lang)

    return (
        quiz_area(
            session["mix_current_question"],
            feedback=fb,
            post_url="/practice-all/answer",
            label=new_label,
            lang=lang,
        ),
        oob_stats,
    )


@rt("/practice-all/reset")
def post_practice_all_reset(session) -> Any:
    lang = _ui_lang(session)
    for key in [k for k in list(session.keys()) if k.startswith("mix_")]:
        del session[key]

    _ensure_mix_session(session)

    if session.get("auth"):
        save_progress(session["auth"], session)

    mod = session.get("mix_current_module", "numbers")
    label = _mix_module_label(session, mod)

    stats = _compute_mix_stats(session)
    oob_stats = stats_panel(stats, [], oob=True, lang=lang)
    return (
        quiz_area(
            session["mix_current_question"],
            post_url="/practice-all/answer",
            label=label,
            lang=lang,
        ),
        oob_stats,
    )


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    serve()
