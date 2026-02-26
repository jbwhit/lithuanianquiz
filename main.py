"""Lithuanian Price Exercise App — adaptive quiz with HTMX partials."""

import logging
from typing import Any

from adaptive import AdaptiveLearning
from age_engine import AgeEngine
from auth import QuizOAuth, auth_client, init_db_tables, save_progress
from fasthtml.common import *
from fastlite import database
from monsterui.all import *
from number_engine import NumberEngine
from quiz import ExerciseEngine, highlight_diff, number_pattern
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

adaptive = AdaptiveLearning(exploration_rate=0.2)
engine = ExerciseEngine(ALL_ROWS, adaptive)
time_engine = TimeEngine()

rows_20 = [r for r in ALL_ROWS if r["number"] <= 20]
number_engine_20 = NumberEngine(rows_20, max_number=20)
number_engine_99 = NumberEngine(ALL_ROWS, max_number=99)

age_rows = [r for r in ALL_ROWS if r["number"] >= 2]
age_engine = AgeEngine(age_rows)

weather_rows = [r for r in ALL_ROWS if r["number"] >= 1]
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


def _not_found(req, exc) -> Any:
    return page_shell(
        Container(
            DivCentered(
                Span("🇱🇹", cls="text-6xl mb-4"),
                H2("Page Not Found", cls=(TextT.xl, TextT.bold)),
                P(
                    "The page you're looking for doesn't exist.",
                    cls=TextPresets.muted_lg,
                ),
                A(
                    UkIcon("arrow-left", cls="mr-2"),
                    "Back to Home",
                    href="/",
                    cls="uk-btn uk-btn-primary mt-6",
                ),
                cls="min-h-[40vh]",
            ),
            cls=(ContainerT.xl, "px-8 py-16"),
        )
    )


app, rt = fast_app(
    hdrs=[*Theme.green.headers(daisy=True), _favicon, _goatcounter],
    secret_key="lithuanian-quiz-2025",
    title="Lithuanian Price Quiz",
    exception_handlers={404: _not_found},
)

oauth = QuizOAuth(app, auth_client)

# ------------------------------------------------------------------
# Session helpers
# ------------------------------------------------------------------


def _ensure_session(session: dict[str, Any]) -> None:
    """Initialise defaults and generate first question if needed."""
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
        ex["exercise_type"], ex["row"]
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
    return page_shell(
        Container(
            DivCentered(
                Span("🇱🇹", cls="text-6xl mb-4"),
                H2("Something Went Wrong", cls=(TextT.xl, TextT.bold)),
                P(
                    "Login failed. This usually happens if you cancel the Google sign-in.",
                    cls=TextPresets.muted_lg,
                ),
                Div(
                    A(
                        UkIcon("rotate-ccw", cls="mr-2"),
                        "Try Again",
                        href="/login",
                        cls="uk-btn uk-btn-primary",
                    ),
                    A(
                        UkIcon("arrow-left", cls="mr-2"),
                        "Back to Home",
                        href="/",
                        cls="uk-btn uk-btn-ghost ml-2",
                    ),
                    cls="mt-6 flex gap-2",
                ),
                cls="min-h-[40vh]",
            ),
            cls=(ContainerT.xl, "px-8 py-16"),
        ),
        user_name=session.get("user_name"),
    )


@rt("/login")
def get_login(req, session) -> Any:
    if session.get("auth"):
        return RedirectResponse("/", status_code=303)
    return page_shell(login_page_content(oauth.login_link(req)))


@rt("/")
def get_home(session) -> Any:
    return page_shell(
        landing_page_content(),
        user_name=session.get("user_name"),
        active_module="home",
    )


@rt("/prices")
def get_prices(session) -> Any:
    _ensure_session(session)
    stats = _compute_stats(session)
    history = session.get("history", [])

    reset_modal = Modal(
        ModalHeader(H3("Reset Progress?")),
        ModalBody(P("This will clear all your history. Are you sure?")),
        ModalFooter(
            Button(
                "Cancel",
                cls=ButtonT.ghost,
                data_uk_toggle="target: #reset-modal",
            ),
            Button(
                "Reset",
                cls=ButtonT.destructive,
                hx_post="/reset",
                hx_target="#quiz-area",
            ),
        ),
        id="reset-modal",
    )

    main_content = Container(
        H2("Lithuanian Price Practice", cls=(TextT.xl, "mb-2")),
        P(
            "Practice expressing prices in Lithuanian. "
            "Type the full answer including the euro word.",
            cls="text-base-content/70 text-sm mb-1",
        ),
        P(
            "Two exercise types: ",
            Strong("Kokia kaina?"),
            " (nominative) and ",
            Strong("Kiek kainuoja?"),
            " (accusative).",
            cls="text-base-content/60 text-xs mb-6",
        ),
        examples_section(),
        quiz_area(session["current_question"]),
        Div(stats_panel(stats, history), cls="mt-6"),
        Button(
            UkIcon("refresh-ccw", cls="mr-2"),
            "Reset Progress",
            cls=(ButtonT.destructive, "mt-6"),
            data_uk_toggle="target: #reset-modal",
        ),
        reset_modal,
        cls=(ContainerT.xl, "px-8 py-8"),
    )

    return page_shell(
        main_content, user_name=session.get("user_name"), active_module="prices"
    )


@rt("/answer")
def post(session, user_answer: str = "") -> Any:
    _ensure_session(session)

    row = engine.get_row(session["row_id"])
    correct_answer = engine.correct_answer(session["exercise_type"], row)
    is_correct = engine.check(user_answer, correct_answer)

    # Update counters
    if is_correct:
        session["correct_count"] = session.get("correct_count", 0) + 1
    else:
        session["incorrect_count"] = session.get("incorrect_count", 0) + 1

    # Build history entry (minimal — diffs regenerated on display)
    diff_u, diff_c = highlight_diff(
        user_answer.strip(), correct_answer.strip(), is_correct
    )
    entry = {
        "question": session["current_question"],
        "answer": user_answer.strip(),
        "correct": is_correct,
        "true_answer": correct_answer.strip(),
    }
    history = session.get("history", [])
    history.append(entry)
    session["history"] = history[-50:]

    # Update adaptive model
    exercise_info = {
        "exercise_type": session["exercise_type"],
        "number_pattern": session.get("number_pattern"),
        "grammatical_case": session.get("grammatical_case"),
    }
    adaptive.update(session, exercise_info, is_correct)

    # Pick next question
    _new_question(session)

    # Persist progress (only when logged in)
    if session.get("auth"):
        save_progress(session["auth"], session)

    # Build feedback
    if is_correct:
        fb = feedback_correct(
            user_answer.strip(),
            exercise_type=exercise_info["exercise_type"],
            grammatical_case=exercise_info["grammatical_case"],
        )
    else:
        fb = feedback_incorrect(
            user_answer.strip(),
            correct_answer.strip(),
            diff_u,
            diff_c,
            exercise_type=exercise_info["exercise_type"],
            grammatical_case=exercise_info["grammatical_case"],
            number_pattern=exercise_info["number_pattern"],
            row=row,
        )

    # Return quiz area + OOB stats update
    stats = _compute_stats(session)
    oob_stats = Div(
        stats_panel(stats, session.get("history", [])),
        hx_swap_oob="true",
        id="stats-panel",
    )

    return (
        quiz_area(session["current_question"], feedback=fb),
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
    for key in _PRICE_SESSION_KEYS & set(session.keys()):
        del session[key]

    _ensure_session(session)

    if session.get("auth"):
        save_progress(session["auth"], session)

    stats = _compute_stats(session)
    oob_stats = Div(
        stats_panel(stats, []),
        hx_swap_oob="true",
        id="stats-panel",
    )
    return (
        quiz_area(session["current_question"]),
        oob_stats,
    )


@rt("/stats")
def get_stats(session) -> Any:
    _ensure_session(session)
    _ensure_time_session(session)
    _ensure_number_session(session, number_engine_20, "n20")
    _ensure_number_session(session, number_engine_99, "n99", seed_prefix="n20")
    _ensure_age_session(session)
    _ensure_weather_session(session)
    stats = _compute_stats(session)
    time_stats = _compute_time_stats(session)
    n20_stats = _compute_number_stats(session, "n20", number_engine_20)
    n99_stats = _compute_number_stats(session, "n99", number_engine_99)
    age_stats = _compute_age_stats(session)
    weather_stats = _compute_weather_stats(session)
    return page_shell(
        stats_page_content(
            stats,
            session,
            time_stats=time_stats,
            n20_stats=n20_stats,
            n99_stats=n99_stats,
            age_stats=age_stats,
            weather_stats=weather_stats,
        ),
        user_name=session.get("user_name"),
    )


@rt("/about")
def get_about(session) -> Any:
    return page_shell(
        about_page_content(),
        user_name=session.get("user_name"),
    )


# ------------------------------------------------------------------
# Time routes
# ------------------------------------------------------------------


@rt("/time")
def get_time(session) -> Any:
    _ensure_time_session(session)
    stats = _compute_time_stats(session)
    history = session.get("time_history", [])

    reset_modal = Modal(
        ModalHeader(H3("Reset Progress?")),
        ModalBody(P("This will clear all your time practice history. Are you sure?")),
        ModalFooter(
            Button(
                "Cancel",
                cls=ButtonT.ghost,
                data_uk_toggle="target: #reset-modal",
            ),
            Button(
                "Reset",
                cls=ButtonT.destructive,
                hx_post="/time/reset",
                hx_target="#quiz-area",
            ),
        ),
        id="reset-modal",
    )

    main_content = Container(
        H2("Lithuanian Time Practice", cls=(TextT.xl, "mb-2")),
        P(
            "Practice expressing time in Lithuanian. Type the full answer.",
            cls="text-base-content/70 text-sm mb-1",
        ),
        P(
            "Four exercise types: ",
            Strong("whole hours"),
            ", ",
            Strong("half past"),
            ", ",
            Strong("quarter past"),
            ", and ",
            Strong("quarter to"),
            ".",
            cls="text-base-content/60 text-xs mb-6",
        ),
        time_examples_section(),
        quiz_area(
            session["time_current_question"], post_url="/time/answer", label="Time"
        ),
        Div(stats_panel(stats, history), cls="mt-6"),
        Button(
            UkIcon("refresh-ccw", cls="mr-2"),
            "Reset Progress",
            cls=(ButtonT.destructive, "mt-6"),
            data_uk_toggle="target: #reset-modal",
        ),
        reset_modal,
        cls=(ContainerT.xl, "px-8 py-8"),
    )

    return page_shell(
        main_content, user_name=session.get("user_name"), active_module="time"
    )


@rt("/time/answer")
def post_time_answer(session, user_answer: str = "") -> Any:
    _ensure_time_session(session)

    correct_answer = time_engine.correct_answer(
        session["time_exercise_type"],
        session["time_hour"],
        session["time_minute"],
    )
    is_correct = time_engine.check(user_answer, correct_answer)

    if is_correct:
        session["time_correct_count"] = session.get("time_correct_count", 0) + 1
    else:
        session["time_incorrect_count"] = session.get("time_incorrect_count", 0) + 1

    diff_u, diff_c = highlight_diff(
        user_answer.strip(), correct_answer.strip(), is_correct
    )
    entry = {
        "question": session["time_current_question"],
        "answer": user_answer.strip(),
        "correct": is_correct,
        "true_answer": correct_answer.strip(),
    }
    history = session.get("time_history", [])
    history.append(entry)
    session["time_history"] = history[-50:]

    exercise_info = {
        "exercise_type": session["time_exercise_type"],
        "number_pattern": session.get("time_number_pattern"),
        "grammatical_case": session.get("time_grammatical_case"),
    }
    time_engine.update(session, exercise_info, is_correct)

    answered_hour = session["time_hour"]
    _new_time_question(session)

    # Persist progress (only when logged in)
    if session.get("auth"):
        save_progress(session["auth"], session)

    if is_correct:
        fb = feedback_correct(
            user_answer.strip(),
            exercise_type=exercise_info["exercise_type"],
            grammatical_case=exercise_info["grammatical_case"],
        )
    else:
        fb = feedback_incorrect(
            user_answer.strip(),
            correct_answer.strip(),
            diff_u,
            diff_c,
            exercise_type=exercise_info["exercise_type"],
            grammatical_case=exercise_info["grammatical_case"],
            number_pattern=exercise_info["number_pattern"],
            hour=answered_hour,
        )

    stats = _compute_time_stats(session)
    oob_stats = Div(
        stats_panel(stats, session.get("time_history", [])),
        hx_swap_oob="true",
        id="stats-panel",
    )

    return (
        quiz_area(
            session["time_current_question"],
            feedback=fb,
            post_url="/time/answer",
            label="Time",
        ),
        oob_stats,
    )


@rt("/time/reset")
def post_time_reset(session) -> Any:
    for key in [k for k in list(session.keys()) if k.startswith("time_")]:
        del session[key]

    _ensure_time_session(session)

    if session.get("auth"):
        save_progress(session["auth"], session)

    stats = _compute_time_stats(session)
    oob_stats = Div(
        stats_panel(stats, []),
        hx_swap_oob="true",
        id="stats-panel",
    )
    return (
        quiz_area(
            session["time_current_question"], post_url="/time/answer", label="Time"
        ),
        oob_stats,
    )


# ------------------------------------------------------------------
# Age session helpers
# ------------------------------------------------------------------


def _ensure_age_session(session: dict[str, Any]) -> None:
    """Initialise age module defaults and generate first question if needed."""
    session.setdefault("age_history", [])
    session.setdefault("age_correct_count", 0)
    session.setdefault("age_incorrect_count", 0)
    age_engine.init_tracking(session, "age", seed_prefix="n99")
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
        ex["exercise_type"], ex["row"], ex["pronoun"]
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
    session.setdefault("weather_history", [])
    session.setdefault("weather_correct_count", 0)
    session.setdefault("weather_incorrect_count", 0)
    weather_engine.init_tracking(session, "weather", seed_prefix="n99")
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
        ex["exercise_type"], ex["row"], ex["negative"]
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
    _ensure_age_session(session)
    stats = _compute_age_stats(session)
    history = session.get("age_history", [])

    reset_modal = Modal(
        ModalHeader(H3("Reset Progress?")),
        ModalBody(P("This will clear all your age practice history. Are you sure?")),
        ModalFooter(
            Button(
                "Cancel",
                cls=ButtonT.ghost,
                data_uk_toggle="target: #reset-modal",
            ),
            Button(
                "Reset",
                cls=ButtonT.destructive,
                hx_post="/age/reset",
                hx_target="#quiz-area",
            ),
        ),
        id="reset-modal",
    )

    main_content = Container(
        H2("Lithuanian Age Practice", cls=(TextT.xl, "mb-2")),
        P(
            "Practice expressing ages in Lithuanian with dative pronouns.",
            cls="text-base-content/70 text-sm mb-1",
        ),
        P(
            "Two exercise types: ",
            Strong("produce"),
            " (say the age in Lithuanian) and ",
            Strong("recognize"),
            " (identify the age from Lithuanian).",
            cls="text-base-content/60 text-xs mb-6",
        ),
        age_examples_section(),
        quiz_area(
            session["age_current_question"],
            post_url="/age/answer",
            label="Age",
        ),
        Div(stats_panel(stats, history), cls="mt-6"),
        Button(
            UkIcon("refresh-ccw", cls="mr-2"),
            "Reset Progress",
            cls=(ButtonT.destructive, "mt-6"),
            data_uk_toggle="target: #reset-modal",
        ),
        reset_modal,
        cls=(ContainerT.xl, "px-8 py-8"),
    )

    return page_shell(
        main_content, user_name=session.get("user_name"), active_module="age"
    )


@rt("/age/answer")
def post_age_answer(session, user_answer: str = "") -> Any:
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
    is_correct = age_engine.check(user_answer, correct, ex_type)

    if is_correct:
        session["age_correct_count"] = session.get("age_correct_count", 0) + 1
    else:
        session["age_incorrect_count"] = session.get("age_incorrect_count", 0) + 1

    diff_u, diff_c = highlight_diff(user_answer.strip(), correct.strip(), is_correct)
    entry = {
        "question": session["age_current_question"],
        "answer": user_answer.strip(),
        "correct": is_correct,
        "true_answer": correct.strip(),
    }
    history = session.get("age_history", [])
    history.append(entry)
    session["age_history"] = history[-50:]

    exercise_info = {
        "exercise_type": ex_type,
        "number_pattern": session.get("age_number_pattern"),
        "pronoun": pronoun_dative,
    }
    age_engine.update(session, "age", exercise_info, is_correct)

    _new_age_question(session)

    if session.get("auth"):
        save_progress(session["auth"], session)

    if is_correct:
        fb = feedback_correct(user_answer.strip(), exercise_type=ex_type)
    else:
        fb = feedback_incorrect(
            user_answer.strip(),
            correct.strip(),
            diff_u,
            diff_c,
            exercise_type=ex_type,
            number_pattern=exercise_info["number_pattern"],
        )

    stats = _compute_age_stats(session)
    oob_stats = Div(
        stats_panel(stats, session.get("age_history", [])),
        hx_swap_oob="true",
        id="stats-panel",
    )

    return (
        quiz_area(
            session["age_current_question"],
            feedback=fb,
            post_url="/age/answer",
            label="Age",
        ),
        oob_stats,
    )


@rt("/age/reset")
def post_age_reset(session) -> Any:
    for key in [k for k in list(session.keys()) if k.startswith("age_")]:
        del session[key]

    _ensure_age_session(session)

    if session.get("auth"):
        save_progress(session["auth"], session)

    stats = _compute_age_stats(session)
    oob_stats = Div(
        stats_panel(stats, []),
        hx_swap_oob="true",
        id="stats-panel",
    )
    return (
        quiz_area(
            session["age_current_question"],
            post_url="/age/answer",
            label="Age",
        ),
        oob_stats,
    )


# ------------------------------------------------------------------
# Weather routes
# ------------------------------------------------------------------


@rt("/weather")
def get_weather(session) -> Any:
    _ensure_weather_session(session)
    stats = _compute_weather_stats(session)
    history = session.get("weather_history", [])

    reset_modal = Modal(
        ModalHeader(H3("Reset Progress?")),
        ModalBody(
            P("This will clear all your weather practice history. Are you sure?")
        ),
        ModalFooter(
            Button(
                "Cancel",
                cls=ButtonT.ghost,
                data_uk_toggle="target: #reset-modal",
            ),
            Button(
                "Reset",
                cls=ButtonT.destructive,
                hx_post="/weather/reset",
                hx_target="#quiz-area",
            ),
        ),
        id="reset-modal",
    )

    main_content = Container(
        H2("Lithuanian Weather Practice", cls=(TextT.xl, "mb-2")),
        P(
            "Practice expressing temperatures in Lithuanian.",
            cls="text-base-content/70 text-sm mb-1",
        ),
        P(
            "Two exercise types: ",
            Strong("produce"),
            " (say the temperature in Lithuanian) and ",
            Strong("recognize"),
            " (identify the temperature from Lithuanian).",
            cls="text-base-content/60 text-xs mb-6",
        ),
        weather_examples_section(),
        quiz_area(
            session["weather_current_question"],
            post_url="/weather/answer",
            label="Weather",
        ),
        Div(stats_panel(stats, history), cls="mt-6"),
        Button(
            UkIcon("refresh-ccw", cls="mr-2"),
            "Reset Progress",
            cls=(ButtonT.destructive, "mt-6"),
            data_uk_toggle="target: #reset-modal",
        ),
        reset_modal,
        cls=(ContainerT.xl, "px-8 py-8"),
    )

    return page_shell(
        main_content, user_name=session.get("user_name"), active_module="weather"
    )


@rt("/weather/answer")
def post_weather_answer(session, user_answer: str = "") -> Any:
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
    is_correct = weather_engine.check(user_answer, correct, ex_type)

    if is_correct:
        session["weather_correct_count"] = session.get("weather_correct_count", 0) + 1
    else:
        session["weather_incorrect_count"] = (
            session.get("weather_incorrect_count", 0) + 1
        )

    diff_u, diff_c = highlight_diff(user_answer.strip(), correct.strip(), is_correct)
    entry = {
        "question": session["weather_current_question"],
        "answer": user_answer.strip(),
        "correct": is_correct,
        "true_answer": correct.strip(),
    }
    history = session.get("weather_history", [])
    history.append(entry)
    session["weather_history"] = history[-50:]

    exercise_info = {
        "exercise_type": ex_type,
        "number_pattern": session.get("weather_number_pattern"),
        "sign": "negative" if negative else "positive",
    }
    weather_engine.update(session, "weather", exercise_info, is_correct)

    _new_weather_question(session)

    if session.get("auth"):
        save_progress(session["auth"], session)

    if is_correct:
        fb = feedback_correct(user_answer.strip(), exercise_type=ex_type)
    else:
        fb = feedback_incorrect(
            user_answer.strip(),
            correct.strip(),
            diff_u,
            diff_c,
            exercise_type=ex_type,
            number_pattern=exercise_info["number_pattern"],
        )

    stats = _compute_weather_stats(session)
    oob_stats = Div(
        stats_panel(stats, session.get("weather_history", [])),
        hx_swap_oob="true",
        id="stats-panel",
    )

    return (
        quiz_area(
            session["weather_current_question"],
            feedback=fb,
            post_url="/weather/answer",
            label="Weather",
        ),
        oob_stats,
    )


@rt("/weather/reset")
def post_weather_reset(session) -> Any:
    for key in [k for k in list(session.keys()) if k.startswith("weather_")]:
        del session[key]

    _ensure_weather_session(session)

    if session.get("auth"):
        save_progress(session["auth"], session)

    stats = _compute_weather_stats(session)
    oob_stats = Div(
        stats_panel(stats, []),
        hx_swap_oob="true",
        id="stats-panel",
    )
    return (
        quiz_area(
            session["weather_current_question"],
            post_url="/weather/answer",
            label="Weather",
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
    title: str,
    subtitle: str,
    module_name: str,
    seed_prefix: str | None = None,
) -> None:
    """Register GET/POST routes for a number module."""

    @rt(route_base)
    def get_numbers(session) -> Any:
        _ensure_number_session(session, engine_inst, prefix, seed_prefix=seed_prefix)
        stats = _compute_number_stats(session, prefix, engine_inst)
        history = session.get(f"{prefix}_history", [])

        reset_modal = Modal(
            ModalHeader(H3("Reset Progress?")),
            ModalBody(
                P("This will clear all your number practice history. Are you sure?")
            ),
            ModalFooter(
                Button(
                    "Cancel",
                    cls=ButtonT.ghost,
                    data_uk_toggle="target: #reset-modal",
                ),
                Button(
                    "Reset",
                    cls=ButtonT.destructive,
                    hx_post=f"{route_base}/reset",
                    hx_target="#quiz-area",
                ),
            ),
            id="reset-modal",
        )

        main_content = Container(
            H2(title, cls=(TextT.xl, "mb-2")),
            P(
                subtitle,
                cls="text-base-content/70 text-sm mb-1",
            ),
            P(
                "Two exercise types: ",
                Strong("produce"),
                " (say the number in Lithuanian) and ",
                Strong("recognize"),
                " (identify the number from Lithuanian).",
                cls="text-base-content/60 text-xs mb-6",
            ),
            number_examples_section(engine_inst.max_number),
            quiz_area(
                session[f"{prefix}_current_question"],
                post_url=f"{route_base}/answer",
                label="Numbers",
            ),
            Div(stats_panel(stats, history), cls="mt-6"),
            Button(
                UkIcon("refresh-ccw", cls="mr-2"),
                "Reset Progress",
                cls=(ButtonT.destructive, "mt-6"),
                data_uk_toggle="target: #reset-modal",
            ),
            reset_modal,
            cls=(ContainerT.xl, "px-8 py-8"),
        )

        return page_shell(
            main_content, user_name=session.get("user_name"), active_module=module_name
        )

    @rt(f"{route_base}/answer")
    def post_number_answer(session, user_answer: str = "") -> Any:
        _ensure_number_session(session, engine_inst, prefix, seed_prefix=seed_prefix)

        row_id = session[f"{prefix}_row_id"]
        ex_type = session[f"{prefix}_exercise_type"]
        row = engine_inst.rows[0]  # fallback
        for r in engine_inst.rows:
            if r["number"] == row_id:
                row = r
                break

        correct = engine_inst.correct_answer(ex_type, row)
        is_correct = engine_inst.check(user_answer, correct, ex_type)

        if is_correct:
            session[f"{prefix}_correct_count"] = (
                session.get(f"{prefix}_correct_count", 0) + 1
            )
        else:
            session[f"{prefix}_incorrect_count"] = (
                session.get(f"{prefix}_incorrect_count", 0) + 1
            )

        diff_u, diff_c = highlight_diff(
            user_answer.strip(), correct.strip(), is_correct
        )
        entry = {
            "question": session[f"{prefix}_current_question"],
            "answer": user_answer.strip(),
            "correct": is_correct,
            "true_answer": correct.strip(),
        }
        history = session.get(f"{prefix}_history", [])
        history.append(entry)
        session[f"{prefix}_history"] = history[-50:]

        exercise_info = {
            "exercise_type": ex_type,
            "number_pattern": session.get(f"{prefix}_number_pattern"),
        }
        engine_inst.update(session, prefix, exercise_info, is_correct)

        _new_number_question(session, engine_inst, prefix)

        if session.get("auth"):
            save_progress(session["auth"], session)

        if is_correct:
            fb = feedback_correct(user_answer.strip(), exercise_type=ex_type)
        else:
            fb = feedback_incorrect(
                user_answer.strip(),
                correct.strip(),
                diff_u,
                diff_c,
                exercise_type=ex_type,
                number_pattern=exercise_info["number_pattern"],
            )

        stats = _compute_number_stats(session, prefix, engine_inst)
        oob_stats = Div(
            stats_panel(stats, session.get(f"{prefix}_history", [])),
            hx_swap_oob="true",
            id="stats-panel",
        )

        return (
            quiz_area(
                session[f"{prefix}_current_question"],
                feedback=fb,
                post_url=f"{route_base}/answer",
                label="Numbers",
            ),
            oob_stats,
        )

    @rt(f"{route_base}/reset")
    def post_number_reset(session) -> Any:
        for key in [k for k in list(session.keys()) if k.startswith(f"{prefix}_")]:
            del session[key]

        _ensure_number_session(session, engine_inst, prefix, seed_prefix=seed_prefix)

        if session.get("auth"):
            save_progress(session["auth"], session)

        stats = _compute_number_stats(session, prefix, engine_inst)
        oob_stats = Div(
            stats_panel(stats, []),
            hx_swap_oob="true",
            id="stats-panel",
        )
        return (
            quiz_area(
                session[f"{prefix}_current_question"],
                post_url=f"{route_base}/answer",
                label="Numbers",
            ),
            oob_stats,
        )


_make_number_routes(
    number_engine_20,
    "n20",
    "/numbers-20",
    "Lithuanian Numbers 1-20",
    "Learn the basic Lithuanian number words.",
    "numbers-20",
)
_make_number_routes(
    number_engine_99,
    "n99",
    "/numbers-99",
    "Lithuanian Numbers 1-99",
    "All numbers including decades and compounds.",
    "numbers-99",
    seed_prefix="n20",
)


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    serve()
