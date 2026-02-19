"""Tests for quiz.py — exercise engine."""

import pytest

from quiz import (
    ExerciseEngine,
    highlight_diff,
    normalize,
    number_pattern,
)

# ------------------------------------------------------------------
# normalize
# ------------------------------------------------------------------


class TestNormalize:
    def test_strips_whitespace(self) -> None:
        assert normalize("  hello  ") == "hello"

    def test_lowercases(self) -> None:
        assert normalize("HELLO") == "hello"

    def test_removes_trailing_period(self) -> None:
        assert normalize("vienas euras.") == "vienas euras"

    def test_collapses_spaces(self) -> None:
        assert normalize("du   eurai") == "du eurai"

    def test_combined(self) -> None:
        assert normalize("  Du   Eurai. ") == "du eurai"


# ------------------------------------------------------------------
# number_pattern
# ------------------------------------------------------------------


class TestNumberPattern:
    def test_single_digit(self) -> None:
        for n in (1, 5, 9):
            assert number_pattern(n) == "single_digit"

    def test_teens(self) -> None:
        for n in (10, 13, 19):
            assert number_pattern(n) == "teens"

    def test_decade(self) -> None:
        for n in (20, 30, 50):
            assert number_pattern(n) == "decade"

    def test_compound(self) -> None:
        for n in (21, 37, 99):
            assert number_pattern(n) == "compound"


# ------------------------------------------------------------------
# highlight_diff
# ------------------------------------------------------------------


class TestHighlightDiff:
    def test_correct_wraps_in_success(self) -> None:
        u, c = highlight_diff("vienas euras.", "vienas euras.", True)
        assert "text-success" in u
        assert "<span" not in c

    def test_incorrect_shows_error_spans(self) -> None:
        u, c = highlight_diff("du euro", "du eurai", False)
        assert "text-error" in u
        assert "text-success" in c


# ------------------------------------------------------------------
# ExerciseEngine
# ------------------------------------------------------------------


SAMPLE_ROW = {
    "number": 1,
    "kokia_kaina": "vienas",
    "kokia_kaina_compound": None,
    "euro_nom": "euras",
    "kiek_kainuoja": "vieną",
    "kiek_kainuoja_compound": None,
    "euro_acc": "eurą",
}

SAMPLE_COMPOUND_ROW = {
    "number": 21,
    "kokia_kaina": "dvidešimt",
    "kokia_kaina_compound": "vienas",
    "euro_nom": "euras",
    "kiek_kainuoja": "dvidešimt",
    "kiek_kainuoja_compound": "vieną",
    "euro_acc": "eurą",
}


class TestExerciseEngine:
    @pytest.fixture()
    def engine(self) -> ExerciseEngine:
        return ExerciseEngine([SAMPLE_ROW, SAMPLE_COMPOUND_ROW])

    def test_correct_answer_kokia(self, engine: ExerciseEngine) -> None:
        ans = engine.correct_answer("kokia", SAMPLE_ROW)
        assert ans == "vienas euras."

    def test_correct_answer_kiek(self, engine: ExerciseEngine) -> None:
        ans = engine.correct_answer("kiek", SAMPLE_ROW)
        assert ans == "vieną eurą."

    def test_correct_answer_compound_kokia(
        self, engine: ExerciseEngine
    ) -> None:
        ans = engine.correct_answer("kokia", SAMPLE_COMPOUND_ROW)
        assert ans == "dvidešimt vienas euras."

    def test_correct_answer_compound_kiek(
        self, engine: ExerciseEngine
    ) -> None:
        ans = engine.correct_answer("kiek", SAMPLE_COMPOUND_ROW)
        assert ans == "dvidešimt vieną eurą."

    def test_format_question_kokia(self, engine: ExerciseEngine) -> None:
        q = engine.format_question("kokia", "€1", None)
        assert q == "Kokia kaina? (€1)"

    def test_format_question_kiek(self, engine: ExerciseEngine) -> None:
        q = engine.format_question("kiek", "€5", "knyga")
        assert q == "Kiek kainuoja knyga? (€5)"

    def test_check_correct(self, engine: ExerciseEngine) -> None:
        assert engine.check("vienas euras.", "vienas euras.") is True

    def test_check_case_insensitive(self, engine: ExerciseEngine) -> None:
        assert engine.check("Vienas Euras", "vienas euras.") is True

    def test_check_incorrect(self, engine: ExerciseEngine) -> None:
        assert engine.check("du eurai", "vienas euras.") is False

    def test_get_row(self, engine: ExerciseEngine) -> None:
        assert engine.get_row(1) == SAMPLE_ROW

    def test_generate_returns_dict(self, engine: ExerciseEngine) -> None:
        ex = engine.generate({})
        assert "exercise_type" in ex
        assert "row" in ex
        assert "price" in ex
