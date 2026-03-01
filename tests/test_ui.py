"""Tests for ui.py — quiz area and HTMX swap behaviour."""

from fasthtml.common import to_xml
from ui import feedback_incorrect, quiz_area


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
