"""UI component functions for Lithuanian price quiz."""

from typing import Any

from fasthtml.common import *
from monsterui.all import *
from quiz import highlight_diff

# ------------------------------------------------------------------
# Page shell
# ------------------------------------------------------------------


def page_shell(*content: Any, user_name: str | None = None) -> Div:
    """Full page wrapper with navbar."""
    brand = DivLAligned(
        Span("🇱🇹", cls="text-2xl mr-2"),
        H3("Lithuanian", cls=(TextT.xl, TextT.bold, "text-primary")),
        P("Price Exercises", cls=TextT.muted),
        cls="items-center",
    )
    nav_items: list[Any] = [
        A("Home", href="/", cls="uk-btn uk-btn-ghost"),
        A("About", href="/about", cls="uk-btn uk-btn-ghost"),
        A("Stats", href="/stats", cls="uk-btn uk-btn-ghost"),
    ]
    if user_name:
        nav_items.extend([
            Span(user_name, cls=(TextT.sm, "px-3 py-2")),
            A("Logout", href="/logout", cls="uk-btn uk-btn-ghost"),
        ])
    else:
        nav_items.append(A("Login", href="/login", cls="uk-btn uk-btn-ghost"))
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


def login_page_content(login_url: str) -> Container:
    """Centered login card."""
    return Container(
        DivCentered(
            Card(
                CardHeader(
                    DivCentered(
                        Span("🇱🇹", cls="text-5xl mb-3"),
                        H2(
                            "Lithuanian Price Quiz",
                            cls=(TextT.xl, TextT.bold),
                        ),
                        P(
                            "Practice expressing prices in Lithuanian",
                            cls=TextPresets.muted_lg,
                        ),
                    )
                ),
                CardBody(
                    DivCentered(
                        A(
                            UkIcon("log-in", cls="mr-2"),
                            "Login with Google",
                            href=login_url,
                            cls=(ButtonT.primary, "px-8 py-3 text-lg"),
                        ),
                        P(
                            "Free and private. We only store your quiz "
                            "progress — nothing else.",
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


# ------------------------------------------------------------------
# Quiz area (HTMX target)
# ------------------------------------------------------------------


def quiz_area(
    question: str,
    feedback: Any | None = None,
) -> Div:
    """Card with question + answer form, optional feedback alert above."""
    form = Form(
        Input(
            id="user_answer",
            name="user_answer",
            placeholder="Type your answer in Lithuanian...",
            autofocus=True,
            autocomplete="off",
            cls="uk-input uk-form-large w-full",
        ),
        DivRAligned(
            Button(
                UkIcon("send", cls="mr-2"),
                "Submit",
                type="submit",
                cls=(ButtonT.primary, "px-6 mt-4"),
            )
        ),
        hx_post="/answer",
        hx_target="#quiz-area",
    )

    card = Card(
        CardHeader(
            DivFullySpaced(
                H3("Current Exercise", cls=TextT.lg),
                Label("Practice", cls=LabelT.primary),
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

_CASE_LABELS: dict[str, str] = {
    "nominative": "nominative case (vardininkas)",
    "accusative": "accusative case (galininkas)",
}
_TYPE_LABELS: dict[str, str] = {
    "kokia": "Kokia kaina?",
    "kiek": "Kiek kainuoja?",
}
_GRAMMAR_HINTS: dict[str, str] = {
    "nominative": "Nominative: used when stating a price (Kokia kaina?).",
    "accusative": "Accusative: used when saying what something costs (Kiek kainuoja?).",
}


def _exercise_context_text(
    exercise_type: str | None,
    grammatical_case: str | None,
) -> str:
    """One-line description of what this exercise tested."""
    parts = []
    if exercise_type:
        parts.append(_TYPE_LABELS.get(exercise_type, exercise_type))
    if grammatical_case:
        parts.append(_CASE_LABELS.get(grammatical_case, grammatical_case))
    return " — ".join(parts)


def feedback_correct(
    user_answer: str,
    exercise_type: str | None = None,
    grammatical_case: str | None = None,
) -> Div:
    """Green inline alert for correct answer."""
    ctx = _exercise_context_text(exercise_type, grammatical_case)
    return Div(
        DivLAligned(
            UkIcon("check-circle", cls="text-success mr-2"),
            Div(
                P("Correct!", cls=(TextT.bold, "text-success")),
                P(f"Your answer: {user_answer}", cls=TextT.sm),
                *(
                    [P(ctx, cls="text-base-content/60 text-xs mt-1")]
                    if ctx
                    else []
                ),
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
) -> Div:
    """Red inline alert with diff highlighting and grammar context."""
    ctx = _exercise_context_text(exercise_type, grammatical_case)
    hint = _GRAMMAR_HINTS.get(grammatical_case or "")
    return Div(
        DivLAligned(
            UkIcon(
                "x-circle", cls="text-error mr-2", height=24, width=24
            ),
            Div(
                P("Not quite right", cls=(TextT.bold, "text-error")),
            ),
        ),
        Div(
            P("Your answer:", cls=(TextT.bold, "text-sm mt-2")),
            P(NotStr(diff_user), cls="ml-4"),
            P("Correct answer:", cls=(TextT.bold, "text-sm mt-2")),
            P(NotStr(diff_correct), cls="ml-4"),
            cls="mt-2",
        ),
        *(
            [Div(
                P(ctx, cls="text-sm font-medium text-base-content/70"),
                *(
                    [P(hint, cls="text-xs text-base-content/60 italic mt-1")]
                    if hint
                    else []
                ),
                cls="border-t border-base-content/10 pt-3 mt-3",
            )]
            if ctx
            else []
        ),
        cls="mb-4 p-4 rounded-lg border-2 border-error/40 bg-error/20 text-base-content",
    )


# ------------------------------------------------------------------
# Stats panel (sidebar / OOB)
# ------------------------------------------------------------------


def _stat_metric(
    icon: str, value: str, label: str, color: str = "text-primary"
) -> Div:
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


def _accuracy_bar(accuracy: float) -> Div:
    color = (
        "bg-error"
        if accuracy < 60
        else "bg-warning"
        if accuracy < 80
        else "bg-success"
    )
    return Div(
        P(f"Accuracy: {accuracy:.1f}%", cls=(TextT.bold, "mb-1")),
        Progress(
            value=int(min(100, accuracy)),
            max=100,
            cls=f"h-3 rounded-full {color}",
        ),
        cls="mt-4 space-y-2",
    )


def _weak_area_item(area: dict[str, Any]) -> Li:
    rate = area["success_rate"] * 100
    color = (
        "bg-error"
        if rate < 60
        else "bg-warning"
        if rate < 80
        else "bg-success"
    )
    return Li(
        Div(
            P(
                area["name"].replace("_", " ").title(),
                cls=TextT.medium,
            ),
            Progress(
                value=int(rate), max=100, cls=f"h-2 rounded-full {color}"
            ),
            P(f"{rate:.1f}%", cls=TextPresets.muted_sm),
            cls="w-full",
        ),
        cls="mb-3",
    )


def _weak_areas_section(
    weak_areas: dict[str, list[dict[str, Any]]],
) -> Card:
    if not weak_areas:
        body = DivCentered(
            UkIcon(
                "target", height=40, width=40, cls="text-muted mb-2"
            ),
            P("Complete more exercises", cls=TextPresets.muted_sm),
            cls="py-8",
        )
    else:
        sections = []
        for cat, areas in weak_areas.items():
            sections.append(
                Div(
                    H4(cat, cls=(TextT.bold, "mb-2")),
                    Ul(
                        *[_weak_area_item(a) for a in areas],
                        cls="space-y-2",
                    ),
                    cls="mb-4",
                )
            )
        body = Div(*sections)

    return Card(
        CardHeader(
            H3("Areas to Improve", cls=TextT.lg),
            Subtitle("Focus on these areas"),
        ),
        CardBody(body),
        cls="shadow-lg border-t-4 border-t-warning h-full",
    )


def _history_entry(
    entry: dict[str, Any], idx: int, total: int
) -> Div:
    correct = entry["correct"]
    diff_u, diff_c = highlight_diff(
        entry["answer"], entry["true_answer"], correct
    )
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
            P("Your answer:", cls=(TextT.gray, TextT.bold, "text-sm mt-2")),
            P(NotStr(diff_u), cls="ml-4"),
            *(
                [
                    P(
                        "Correct answer:",
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


def _history_card(history: list[dict[str, Any]]) -> Card:
    total = len(history)
    if history:
        items = [
            _history_entry(e, i, total)
            for i, e in enumerate(reversed(history[-5:]))
        ]
        body = Div(*items)
    else:
        body = DivCentered(
            UkIcon(
                "history", height=40, width=40, cls="text-muted mb-2"
            ),
            P("No history yet", cls=TextPresets.muted_lg),
            P(
                "Your exercise history will appear here",
                cls=TextPresets.muted_sm,
            ),
            cls="py-16",
        )
    return Card(
        CardHeader(
            DivFullySpaced(
                H3("Recent Exercises", cls=TextT.lg),
                A(
                    "View All",
                    href="/stats",
                    cls="uk-btn uk-btn-ghost",
                ),
            ),
            Subtitle("Review your previous exercises"),
        ),
        CardBody(body, cls="max-h-[400px] overflow-y-auto pr-2"),
        cls="shadow-lg border-t-4 border-t-accent h-full",
    )


def stats_panel(
    stats: dict[str, Any], history: list[dict[str, Any]]
) -> Div:
    """Full right-side stats panel for OOB swap."""
    metrics = Grid(
        _stat_metric("list", str(stats["total"]), "Total", "text-primary"),
        _stat_metric(
            "check", str(stats["correct"]), "Correct", "text-success"
        ),
        _stat_metric(
            "x", str(stats["incorrect"]), "Incorrect", "text-error"
        ),
        _stat_metric(
            "flame",
            str(stats["current_streak"]),
            "Streak",
            "text-warning",
        ),
        cols=4,
        cols_sm=2,
        gap=4,
        cls="mb-6",
    )
    weak = _weak_areas_section(stats.get("weak_areas", {}))
    hist = _history_card(history)

    return Div(
        metrics,
        _accuracy_bar(stats["accuracy"]),
        Div(cls="mt-6"),
        Grid(
            Div(weak, cls="h-full col-span-1"),
            Div(hist, cls="h-full col-span-1"),
            cols_md=2,
            cols_sm=1,
            gap=6,
        ),
        id="stats-panel",
    )


# ------------------------------------------------------------------
# Performance-by-category card (stats page)
# ------------------------------------------------------------------


def _perf_by_category(
    category_data: dict[str, dict[str, int]], title: str
) -> Card:
    items = []
    for key, s in category_data.items():
        total = s["correct"] + s["incorrect"]
        rate = (s["correct"] / total * 100) if total else 0
        color = (
            "bg-error"
            if rate < 60
            else "bg-warning"
            if rate < 80
            else "bg-success"
        )
        items.append(
            Div(
                P(key.replace("_", " ").title(), cls=TextT.medium),
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
            Subtitle("Performance by category"),
        ),
        CardBody(*items),
        cls="shadow-lg border-t-4 border-t-primary h-full",
    )


# ------------------------------------------------------------------
# Full-page views
# ------------------------------------------------------------------


def stats_page_content(
    stats: dict[str, Any], session: dict[str, Any]
) -> Container:
    """Full stats page body."""
    stats_card = Card(
        CardHeader(
            H3("Your Progress", cls=TextT.lg),
            Subtitle("Track your learning journey"),
        ),
        CardBody(
            Grid(
                _stat_metric(
                    "list", str(stats["total"]), "Total", "text-primary"
                ),
                _stat_metric(
                    "check",
                    str(stats["correct"]),
                    "Correct",
                    "text-success",
                ),
                _stat_metric(
                    "x",
                    str(stats["incorrect"]),
                    "Incorrect",
                    "text-error",
                ),
                _stat_metric(
                    "flame",
                    str(stats["current_streak"]),
                    "Streak",
                    "text-warning",
                ),
                cols=4,
                cols_sm=2,
                gap=4,
                cls="mb-4",
            ),
            _accuracy_bar(stats["accuracy"]),
        ),
        cls="shadow-lg border-t-4 border-t-secondary h-full",
    )

    weak_card = _weak_areas_section(stats.get("weak_areas", {}))

    perf_cards: list[Any] = []
    perf = session.get("performance", {})
    for key, title in [
        ("exercise_types", "Exercise Types"),
        ("number_patterns", "Number Patterns"),
        ("grammatical_cases", "Grammatical Cases"),
    ]:
        if perf.get(key):
            perf_cards.append(_perf_by_category(perf[key], title))

    detail_section = (
        Grid(*perf_cards, cols_md=1, cols_lg=2, cols_xl=3, gap=6)
        if perf_cards
        else DivCentered(
            UkIcon(
                "info", height=40, width=40, cls="text-muted mb-2"
            ),
            P(
                "Complete more exercises to see detailed performance",
                cls=TextPresets.muted_lg,
            ),
            cls="py-8 bg-base-200 rounded-lg mt-4",
        )
    )

    # Full history
    history = session.get("history", [])
    total = len(history)
    if history:
        hist_items = [
            _history_entry(e, i, total)
            for i, e in enumerate(reversed(history))
        ]
        hist_body = Div(*hist_items)
    else:
        hist_body = DivCentered(
            P("No history yet", cls=TextPresets.muted_lg),
            cls="py-8",
        )

    hist_card = Card(
        CardHeader(
            H3("Full History", cls=TextT.lg),
            Subtitle("All your exercises"),
        ),
        CardBody(hist_body, cls="max-h-[600px] overflow-y-auto pr-2"),
        cls="shadow-lg border-t-4 border-t-accent h-full",
    )

    return Container(
        H2("Your Statistics", cls=TextT.xl),
        P("Track your learning progress", cls=TextPresets.muted_lg),
        Div(stats_card, cls="mt-6"),
        Div(weak_card, cls="mt-6"),
        Div(
            H3(
                "Detailed Performance",
                cls=(TextT.lg, "mt-8 mb-4"),
            ),
            detail_section,
            cls="mt-6",
        ),
        Div(hist_card, cls="mt-6"),
        A(
            UkIcon("arrow-left", cls="mr-2"),
            "Back to Practice",
            href="/",
            cls="uk-btn uk-btn-primary mt-8",
        ),
        cls=(ContainerT.xl, "px-8 py-8"),
    )


def about_page_content() -> Container:
    return Container(
        H2("About This App", cls=TextT.xl),
        P(
            "Learn Lithuanian price expressions with this interactive tool!",
            cls=TextPresets.muted_lg,
        ),
        P(
            "This application helps you practice how to express prices "
            "in Lithuanian through interactive exercises.",
            cls="mt-4",
        ),
        P(
            "The app features an adaptive learning system that uses "
            "Thompson sampling to target exercises to your weak areas.",
            cls="mt-4",
        ),
        P("There are two types of exercises:", cls="mt-4"),
        Ul(
            Li(
                Strong("Kokia kaina?"),
                " (What is the price?) — ",
                "Nominative case (vardininkas). State the price directly.",
            ),
            Li(
                Strong("Kiek kainuoja?"),
                " (How much does it cost?) — ",
                "Accusative case (galininkas). The number changes form.",
            ),
            cls="list-disc ml-6 mt-2 space-y-2",
        ),
        P(
            "Practice regularly to improve your Lithuanian language skills!",
            cls="mt-4",
        ),
        A(
            UkIcon("arrow-left", cls="mr-2"),
            "Back to Practice",
            href="/",
            cls="uk-btn uk-btn-primary mt-6",
        ),
        cls=(ContainerT.xl, "px-8 py-8"),
    )
