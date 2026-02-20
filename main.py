"""Lithuanian Price Exercise App — adaptive quiz with HTMX partials."""

import logging
from typing import Any

from adaptive import AdaptiveLearning
from auth import QuizOAuth, auth_client, init_db_tables, save_progress
from fasthtml.common import *
from fastlite import database
from monsterui.all import *
from quiz import ExerciseEngine, highlight_diff, number_pattern
from ui import (
    about_page_content,
    feedback_correct,
    feedback_incorrect,
    login_page_content,
    page_shell,
    quiz_area,
    stats_page_content,
    stats_panel,
)

log = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Data & services (loaded once at startup)
# ------------------------------------------------------------------

_db = database("lithuanian_data.db")
init_db_tables()
ALL_ROWS: list[dict[str, Any]] = list(_db.t["numbers"].rows)

adaptive = AdaptiveLearning(exploration_rate=0.2)
engine = ExerciseEngine(ALL_ROWS, adaptive)

# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------

_favicon = Link(
    rel="icon",
    href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🇱🇹</text></svg>",
)

app, rt = fast_app(
    hdrs=[*Theme.green.headers(daisy=True), _favicon],
    secret_key="lithuanian-quiz-2025",
    title="Lithuanian Price Quiz",
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
        "accusative"
        if ex["exercise_type"] == "kiek"
        else "nominative"
    )
    session["current_question"] = engine.format_question(
        ex["exercise_type"], ex["price"], ex.get("item")
    )


def _compute_stats(session: dict[str, Any]) -> dict[str, Any]:
    corr = session.get("correct_count", 0)
    inc = session.get("incorrect_count", 0)
    tot = corr + inc
    streak = 0
    for entry in reversed(session.get("history", [])):
        if entry["correct"]:
            streak += 1
        else:
            break
    stats: dict[str, Any] = {
        "total": tot,
        "correct": corr,
        "incorrect": inc,
        "accuracy": (corr / tot * 100) if tot else 0,
        "current_streak": streak,
    }
    stats["weak_areas"] = adaptive.get_weak_areas(session)
    return stats


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------


@rt("/login")
def get_login(req, session) -> Any:
    if session.get("auth"):
        return RedirectResponse("/", status_code=303)
    return page_shell(login_page_content(oauth.login_link(req)))


@rt("/")
def get(session) -> Any:
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
        quiz_area(session["current_question"]),
        Div(stats_panel(stats, history), cls="mt-6"),
        Button(
            UkIcon("refresh-ccw", cls="mr-2"),
            "Reset Progress",
            cls=(ButtonT.destructive, "mt-6"),
            data_uk_toggle="target: #reset-modal",
        ),
        Div(
            P(
                UkIcon("shield", cls="inline mr-1", height=14, width=14),
                "Free to use. No tracking beyond your current browser session. ",
                A("Log in", href="/login", cls="underline"),
                " only to save progress across visits.",
                cls="text-base-content/50 text-xs",
            ),
            cls="mt-4 text-center",
        ),
        reset_modal,
        cls=(ContainerT.xl, "px-8 py-8"),
    )

    return page_shell(main_content, user_name=session.get("user_name"))


@rt("/answer")
def post(session, user_answer: str = "") -> Any:
    _ensure_session(session)

    row = engine.get_row(session["row_id"])
    correct_answer = engine.correct_answer(
        session["exercise_type"], row
    )
    is_correct = engine.check(user_answer, correct_answer)

    # Update counters
    if is_correct:
        session["correct_count"] = (
            session.get("correct_count", 0) + 1
        )
    else:
        session["incorrect_count"] = (
            session.get("incorrect_count", 0) + 1
        )

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


@rt("/reset")
def post_reset(session) -> Any:
    # Preserve auth-related keys across reset
    auth = session.get("auth")
    user_name = session.get("user_name")
    user_email = session.get("user_email")

    for key in list(session.keys()):
        del session[key]

    if auth:
        session["auth"] = auth
    if user_name:
        session["user_name"] = user_name
    if user_email:
        session["user_email"] = user_email

    _ensure_session(session)

    if auth:
        save_progress(auth, session)  # Save cleared state to DB

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
    stats = _compute_stats(session)
    return page_shell(
        stats_page_content(stats, session),
        user_name=session.get("user_name"),
    )


@rt("/about")
def get_about(session) -> Any:
    return page_shell(
        about_page_content(),
        user_name=session.get("user_name"),
    )


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    serve()
