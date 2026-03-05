"""Tests for ui.py — quiz area and HTMX swap behaviour."""

from fasthtml.common import to_xml
from ui import feedback_incorrect, page_shell, quiz_area, stats_panel


def _render(component: object) -> str:
    """Render a FastHTML component to an HTML string."""
    return to_xml(component)


class TestQuizAreaHtmxSwap:
    """Ensure HTMX swap attributes prevent duplicate-ID nesting.

    Bug: without hx-swap="outerHTML", the default innerHTML swap nests a
    new div#quiz-area *inside* the existing one, causing duplicate IDs.
    On mobile browsers this leads to stale feedback persisting across
    submissions.
    """

    def test_quiz_area_has_id(self) -> None:
        html = _render(quiz_area("What is 5?"))
        assert 'id="quiz-area"' in html

    def test_form_uses_outer_html_swap(self) -> None:
        """The form must swap outerHTML so the #quiz-area div is *replaced*,
        not filled with a nested duplicate."""
        html = _render(quiz_area("What is 5?"))
        assert 'hx-swap="outerHTML"' in html

    def test_form_targets_quiz_area(self) -> None:
        html = _render(quiz_area("What is 5?"))
        assert 'hx-target="#quiz-area"' in html

    def test_no_duplicate_quiz_area_ids(self) -> None:
        """The returned HTML must contain exactly one element with id=quiz-area."""
        html = _render(
            quiz_area(
                "What is 5?",
                feedback=feedback_incorrect("wrong", "right", "wrong", "right"),
            )
        )
        assert html.count('id="quiz-area"') == 1

    def test_custom_post_url(self) -> None:
        html = _render(quiz_area("What time?", post_url="/time/answer"))
        assert 'hx-post="/time/answer"' in html
        assert 'hx-swap="outerHTML"' in html

    def test_label_displayed(self) -> None:
        html = _render(quiz_area("Q?", label="Age"))
        assert "Age" in html

    def test_feedback_included_when_provided(self) -> None:
        fb = feedback_incorrect("wrong", "right", "wrong", "right")
        html = _render(quiz_area("Next Q?", feedback=fb))
        assert "Not quite right" in html
        assert "Next Q?" in html

    def test_no_feedback_when_none(self) -> None:
        html = _render(quiz_area("Q?"))
        assert "Not quite right" not in html
        assert "Correct!" not in html

    def test_quiz_area_lithuanian_controls(self) -> None:
        html = _render(quiz_area("Klausimas?", lang="lt"))
        assert "Pateikti" in html
        assert "Dabartine Uzduotis" in html
        assert "Irasykite atsakyma lietuviskai" in html


class TestStatsPanelOob:
    """Ensure OOB stats swap doesn't produce duplicate stats-panel IDs."""

    _STATS = {
        "total": 5,
        "correct": 3,
        "incorrect": 2,
        "accuracy": 60.0,
        "current_streak": 1,
        "weak_areas": {},
    }

    def test_stats_panel_has_single_id(self) -> None:
        html = _render(stats_panel(self._STATS, []))
        assert html.count('id="stats-panel"') == 1

    def test_oob_panel_has_single_id(self) -> None:
        """OOB mode must not double-wrap with a second stats-panel id."""
        html = _render(stats_panel(self._STATS, [], oob=True))
        assert html.count('id="stats-panel"') == 1

    def test_oob_panel_has_swap_attr(self) -> None:
        html = _render(stats_panel(self._STATS, [], oob=True))
        assert 'hx-swap-oob="true"' in html

    def test_non_oob_panel_lacks_swap_attr(self) -> None:
        html = _render(stats_panel(self._STATS, []))
        assert "hx-swap-oob" not in html


class TestLanguageToggle:
    def test_page_shell_shows_language_switch_links(self) -> None:
        html = _render(page_shell("X", lang="lt"))
        assert 'href="/set-language?lang=en"' in html
        assert 'href="/set-language?lang=lt"' in html
        assert "Lietuviu" in html

    def test_feedback_incorrect_lithuanian_copy(self) -> None:
        html = _render(
            feedback_incorrect("blogai", "gerai", "blogai", "gerai", lang="lt")
        )
        assert "Jusu atsakymas" in html
        assert "Teisingas atsakymas" in html
