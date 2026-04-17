"""Tests for ui.py — quiz area and HTMX swap behaviour."""

from fasthtml.common import to_xml
from quiz import number_pattern
from ui import (
    examples_section,
    feedback_incorrect,
    page_shell,
    quiz_area,
    stats_panel,
)


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
        assert "Dabartinė Užduotis" in html
        assert "Įrašykite atsakymą lietuviškai" in html


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
        assert "Lietuviškai" in html

    def test_feedback_incorrect_lithuanian_copy(self) -> None:
        html = _render(
            feedback_incorrect("blogai", "gerai", "blogai", "gerai", lang="lt")
        )
        assert "Jūsų atsakymas" in html
        assert "Teisingas atsakymas" in html


class TestDiacriticModeToggle:
    def test_page_shell_defaults_to_strict_mode(self) -> None:
        html = _render(page_shell("X", current_path="/prices", lang="lt"))
        assert "set-diacritic-mode?enabled=0&amp;next_path=/prices" in html
        assert "set-diacritic-mode?enabled=1&amp;next_path=/prices" in html
        assert "Grieztas" in html
        assert "Lankstus" in html
        assert 'uk-active font-bold">Grieztas<' in html
        assert 'uk-active font-bold">Lankstus<' not in html

    def test_examples_section_no_english_leaks_in_lt(self) -> None:
        html = _render(examples_section(lang="lt"))
        assert "Nominative — stating the price directly" not in html
        assert "Vardininkas" in html

    def test_stats_panel_no_english_leaks_in_lt(self) -> None:
        stats = {
            "total": 1,
            "correct": 1,
            "incorrect": 0,
            "accuracy": 100.0,
            "current_streak": 1,
            "weak_areas": {},
        }
        history = [
            {
                "question": "Kokia kaina? (€5)",
                "answer": "penki eurai.",
                "correct": True,
                "true_answer": "penki eurai.",
            }
        ]
        html = _render(stats_panel(stats, history, lang="lt"))
        assert "Recent Exercises" not in html
        assert "užduotys" in html.lower()

    def test_feedback_incorrect_price_grammar_hint_is_localized(self) -> None:
        row = {
            "number": 25,
            "kokia_kaina": "dvidešimt",
            "kokia_kaina_compound": "penki",
            "kiek_kainuoja": "dvidešimt",
            "kiek_kainuoja_compound": "penkis",
            "euro_nom": "eurai",
            "euro_acc": "eurus",
        }
        html = _render(
            feedback_incorrect(
                "blogai",
                "gerai",
                "blogai",
                "gerai",
                exercise_type="kiek",
                grammatical_case="accusative",
                number_pattern="compound",
                row=row,
                lang="lt",
            )
        )
        # English grammar tokens must not appear in LT mode.
        for english_token in (
            "tens part",
            "ones digit",
            "same in both cases",
            "euro,",
            "accusative",
            "nominative",
        ):
            assert english_token not in html, (
                f"English grammar leak in LT mode: {english_token!r}"
            )

    def test_feedback_incorrect_time_grammar_hint_is_localized(self) -> None:
        html = _render(
            feedback_incorrect(
                "blogai",
                "gerai",
                "blogai",
                "gerai",
                exercise_type="quarter_past",
                grammatical_case="genitive",
                hour=2,
                lang="lt",
            )
        )
        for english_token in (
            "quarter past",
            "next hour is",
            "genitive of",
            "nominative of",
        ):
            assert english_token not in html, (
                f"English grammar leak in LT mode: {english_token!r}"
            )

    def test_quiz_area_default_label_is_localized(self) -> None:
        html_en = _render(quiz_area("Klausimas?", lang="en"))
        html_lt = _render(quiz_area("Klausimas?", lang="lt"))
        assert "Practice" in html_en
        assert "Praktika" in html_lt
        assert ">Practice<" not in html_lt

    def test_stats_panel_weak_areas_localized_in_lt(self) -> None:
        stats = {
            "total": 5,
            "correct": 2,
            "incorrect": 3,
            "accuracy": 40.0,
            "current_streak": 0,
            "weak_areas": {
                "Exercise Types": [{"name": "produce", "success_rate": 0.3}],
                "Number Patterns": [{"name": "teens", "success_rate": 0.2}],
                "Grammatical Cases": [{"name": "accusative", "success_rate": 0.4}],
                "Hour Patterns": [{"name": "hour_3", "success_rate": 0.2}],
                "Sign": [{"name": "negative", "success_rate": 0.1}],
            },
        }
        html = _render(stats_panel(stats, [], lang="lt"))
        # Category labels
        for english_label in (
            "Exercise Types",
            "Number Patterns",
            "Grammatical Cases",
            "Hour Patterns",
            ">Sign<",
        ):
            assert english_label not in html, (
                f"English category leak in LT: {english_label!r}"
            )
        # Arm names
        for english_arm in ("Produce", "Teens", "Accusative", "Hour 3", "Negative"):
            assert english_arm not in html, f"English arm leak in LT: {english_arm!r}"
        # Spot-check a localized label rendered
        assert "Kūrimas" in html
        assert "Galininkas" in html

    def test_weak_area_arm_covers_number_pattern_keys(self) -> None:
        """Every arm emitted by quiz.number_pattern() must localize in LT.

        Regression: `number_pattern()` returns `"decade"`, but an earlier
        map had `"round_ten"` so LT renders showed raw `Decade`.
        """
        arms = {number_pattern(n) for n in range(1, 100)}
        assert arms == {"single_digit", "teens", "decade", "compound"}
        stats = {
            "total": 1,
            "correct": 0,
            "incorrect": 1,
            "accuracy": 0.0,
            "current_streak": 0,
            "weak_areas": {
                "Number Patterns": [
                    {"name": arm, "success_rate": 0.2} for arm in sorted(arms)
                ],
            },
        }
        html = _render(stats_panel(stats, [], lang="lt"))
        for english_arm in ("Decade", "Single Digit", "Teens", "Compound"):
            assert english_arm not in html, f"English arm leak in LT: {english_arm!r}"
        # Spot-check the specific one that previously leaked.
        assert "Apvali dešimtis" in html

    def test_feedback_incorrect_time_grammar_hint_english_mode(self) -> None:
        html = _render(
            feedback_incorrect(
                "blogai",
                "gerai",
                "blogai",
                "gerai",
                exercise_type="quarter_past",
                grammatical_case="genitive",
                hour=2,
                lang="en",
            )
        )
        assert "quarter past" in html
        assert "next hour is" in html

    def test_page_shell_marks_tolerant_mode_active(self) -> None:
        html = _render(
            page_shell(
                "X",
                diacritic_tolerant=True,
                current_path="/time",
                lang="lt",
            )
        )
        assert "set-diacritic-mode?enabled=0&amp;next_path=/time" in html
        assert "set-diacritic-mode?enabled=1&amp;next_path=/time" in html
        assert 'uk-active font-bold">Lankstus<' in html
        assert 'uk-active font-bold">Grieztas<' not in html
