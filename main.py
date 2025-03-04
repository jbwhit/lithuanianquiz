"""
Lithuanian Price Exercise App with Adaptive Learning
A language learning tool for practicing Lithuanian price expressions with adaptive learning.
"""
import html
import random
from difflib import SequenceMatcher
from typing import Any, Literal

from adaptive_learning_service import AdaptiveLearningService
from fasthtml.common import *
from fastlite import database
from monsterui.all import *
from session_manager import add_session_cookie, get_session, maybe_cleanup_sessions, save_session

#########################
# 1) Type Definitions
#########################

ExerciseType = Literal["kokia", "kiek"]
SessionData = dict[str, Any]

#########################
# 2) Constants
#########################

EXERCISE_TYPES: list[ExerciseType] = ["kokia", "kiek"]
ITEMS: list[str] = ["knyga", "puodelis", "marškinėliai", "žurnalas", "kepurė"]

REQUIRED_SESSION_KEYS: set = {
    "current_question", "history", "correct_count",
    "incorrect_count", "row_id", "exercise_type",
    "price", "item"
}

#########################
# 3) Database Access
#########################

class DatabaseService:
    """Handles all database operations for the application."""

    def __init__(self, db_path: str = "lithuanian_data.db"):
        """Initialize database connection."""
        self.db = database(db_path)
        self.numbers = self.db.t["numbers"]
        self.attempts = self.db.t["attempts"]
        self._rows_cache = None
        self._row_by_number_cache = {}  # Cache for get_row_by_number lookups

    @property
    def rows(self) -> list[dict[str, Any]]:
        """Get all number rows from database with caching."""
        if self._rows_cache is None:
            self._rows_cache = list(self.numbers.rows)
        return self._rows_cache

    def get_row_by_number(self, number: int) -> dict[str, Any]:
        """Get a specific row by its number value with caching."""
        if number not in self._row_by_number_cache:
            for row in self.rows:
                if row["number"] == number:
                    self._row_by_number_cache[number] = row
                    break
            else:
                raise ValueError(f"No row found for number: {number}")
        return self._row_by_number_cache[number]

#########################
# 5) Exercise Logic
#########################

class ExerciseService:
    """Handles exercise generation and answer validation."""

    def __init__(self, db_service, adaptive_service=None):
        """Initialize with database service and optional adaptive service."""
        self.db = db_service
        self.adaptive = adaptive_service

    def generate_exercise(self, session=None):
        """Generate an exercise, using adaptive learning if session is provided."""
        if session and self.adaptive:
            # Use adaptive learning to select exercise
            exercise = self.adaptive.select_exercise(session, self.db)
            return (
                exercise["exercise_type"],
                exercise["price"],
                exercise["item"],
                exercise["row"]
            )
        else:
            # Fall back to random selection for backward compatibility
            row = random.choice(self.db.rows)
            price = f"€{row['number']}"
            exercise_type = random.choice(EXERCISE_TYPES)
            item = random.choice(ITEMS) if exercise_type == "kiek" else None
            return exercise_type, price, item, row

    def get_correct_answer(self, exercise_type: ExerciseType, row: dict[str, Any]) -> str:
        """Get the correct answer phrase for an exercise."""
        if exercise_type == "kokia":
            if row.get('kokia_kaina_compound'):
                price_phrase = f"{row['kokia_kaina']} {row['kokia_kaina_compound']} {row['euro_nom']}"
            else:
                price_phrase = f"{row['kokia_kaina']} {row['euro_nom']}"
        else:  # 'kiek'
            if row.get('kiek_kainuoja_compound'):
                price_phrase = f"{row['kiek_kainuoja']} {row['kiek_kainuoja_compound']} {row['euro_acc']}"
            else:
                price_phrase = f"{row['kiek_kainuoja']} {row['euro_acc']}"
        return f"{price_phrase}."

    def format_question(self, ex_type: ExerciseType, price: str, item: str | None) -> str:
        """Format question text for display."""
        if ex_type == "kokia":
            return f"Kokia kaina? ({price})"
        else:
            return f"Kiek kainuoja {item}? ({price})"

    def check_answer(self, user_answer: str, correct_answer: str) -> bool:
        """Check if user answer is correct after normalization."""
        return self.normalize_answer(user_answer) == self.normalize_answer(correct_answer)

    @staticmethod
    def normalize_answer(answer: str) -> str:
        """Normalize an answer for comparison."""
        normalized = answer.strip().lower()
        if normalized.endswith('.'):
            normalized = normalized[:-1]
        return ' '.join(normalized.split())

    @staticmethod
    def highlight_differences(user: str, correct: str) -> tuple[str, str]:
        """Compare user vs. correct answers with HTML highlighting."""
        user_esc = html.escape(user)
        corr_esc = html.escape(correct)
        sm = SequenceMatcher(None, user_esc, corr_esc)
        out_user, out_corr = [], []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            seg_u = user_esc[i1:i2]
            seg_c = corr_esc[j1:j2]
            if tag == "equal":
                out_user.append(seg_u)
                out_corr.append(seg_c)
            elif tag == "replace":
                out_user.append(f"<span class='text-error font-bold'>{seg_u}</span>")
                out_corr.append(f"<span class='text-success font-bold'>{seg_c}</span>")
            elif tag == "delete":
                out_user.append(f"<span class='text-error font-bold'>{seg_u}</span>")
            elif tag == "insert":
                out_corr.append(f"<span class='text-success font-bold'>{seg_c}</span>")
        return ("".join(out_user), "".join(out_corr))

#########################
# 6) Session Management
#########################

class SessionManager:
    """Manages session state for the application."""

    def __init__(self, session, exercise_service):
        """Initialize with session object and exercise service."""
        self.session = session
        self.exercise_service = exercise_service

        # Initialize adaptive learning if available
        if hasattr(exercise_service, 'adaptive') and exercise_service.adaptive:
            exercise_service.adaptive.initialize_performance_tracking(session)

    def ensure_initialized(self):
        """Initialize session with default values if needed."""
        defaults = {
            "history": [],
            "correct_count": 0,
            "incorrect_count": 0
        }

        # Update session with defaults for missing keys
        for key, value in defaults.items():
            if key not in self.session:
                self.session[key] = value

        # Generate a question if needed
        if "current_question" not in self.session:
            self.pick_new_question()

        # Initialize adaptive learning
        if hasattr(self.exercise_service, 'adaptive') and self.exercise_service.adaptive:
            self.exercise_service.adaptive.initialize_performance_tracking(self.session)

    def pick_new_question(self):
        """Generate and store a new question in the session using adaptive learning."""
        try:
            # Use session for adaptive learning if available
            ex_type, price, item, row = self.exercise_service.generate_exercise(self.session)

            # Store exercise details for performance tracking
            self.session["exercise_type"] = ex_type
            self.session["price"] = price
            self.session["item"] = item
            self.session["row_id"] = row["number"]

            # Add adaptive learning metadata if the service is available
            if hasattr(self.exercise_service, 'adaptive') and self.exercise_service.adaptive:
                # Determine grammatical case and number pattern for tracking
                self.session["grammatical_case"] = "accusative" if ex_type == "kiek" else "nominative"
                self.session["number_pattern"] = self.exercise_service.adaptive._determine_number_pattern(row["number"])

            # Generate question text
            self.session["current_question"] = self.exercise_service.format_question(ex_type, price, item)
        except Exception as e:
            print(f"Error picking new question: {e}")
            # If anything goes wrong, create a simple fallback question
            self.session["exercise_type"] = "kokia"
            self.session["price"] = "€1"
            self.session["item"] = None
            row = self.exercise_service.db.rows[0]  # Use first row as fallback
            self.session["row_id"] = row["number"]
            self.session["current_question"] = "Kokia kaina? (€1)"

    def record_answer(self, user_answer, correct_answer):
        """Record user answer and update adaptive learning model."""
        try:
            user_str = user_answer.strip()
            correct_str = correct_answer.strip()
            is_correct = self.exercise_service.check_answer(user_str, correct_str)

            diff_user, diff_correct = self._generate_diffs(user_str, correct_str, is_correct)
            self._update_counters(is_correct)
            self._update_history(user_str, correct_str, diff_user, diff_correct, is_correct)
            self._update_adaptive_learning(is_correct)
            self.pick_new_question()
        except Exception as e:
            print(f"Error recording answer: {e}")
            self.reset()

    def _generate_diffs(self, user_str, correct_str, is_correct):
        if is_correct:
            return (f"<span class='text-success font-bold'>{html.escape(user_str)}</span>",
                    html.escape(correct_str))

        user_esc = html.escape(user_str.lower())
        corr_esc = html.escape(correct_str.lower())
        sm = SequenceMatcher(None, user_esc, corr_esc)
        out_user, out_corr = [], []

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            seg_u = html.escape(user_str[i1:i2])
            seg_c = html.escape(correct_str[j1:j2])
            if tag == "equal":
                out_user.append(seg_u)
                out_corr.append(seg_c)
            elif tag == "replace":
                out_user.append(f"<span class='text-error font-bold'>{seg_u}</span>")
                out_corr.append(f"<span class='text-success font-bold'>{seg_c}</span>")
            elif tag == "delete":
                out_user.append(f"<span class='text-error font-bold'>{seg_u}</span>")
            elif tag == "insert":
                out_corr.append(f"<span class='text-success font-bold'>{seg_c}</span>")

        return "".join(out_user), "".join(out_corr)

    def _update_counters(self, is_correct):
        key = "correct_count" if is_correct else "incorrect_count"
        self.session[key] = self.session.get(key, 0) + 1

    def _update_history(self, user_str, correct_str, diff_user, diff_correct, is_correct):
        history_entry = {
            "question": self.session["current_question"],
            "answer": user_str,
            "correct": is_correct,
            "diff_user": diff_user,
            "diff_correct": diff_correct,
            "true_answer": correct_str
        }
        history = self.session.get("history", [])
        history.append(history_entry)
        self.session["history"] = history[-500:]

    def _update_adaptive_learning(self, is_correct):
        if hasattr(self.exercise_service, "adaptive") and self.exercise_service.adaptive:
            try:
                exercise_info = {
                    "exercise_type": self.session["exercise_type"],
                    "grammatical_case": self.session.get("grammatical_case"),
                    "number_pattern": self.session.get("number_pattern"),
                    "row_id": self.session["row_id"]
                }
                self.exercise_service.adaptive.update_performance(self.session, exercise_info, is_correct)
            except Exception as e:
                print(f"Error updating adaptive model: {e}")

    def reset(self):
        """Clear session and initialize a new question."""
        # Only keep certain keys when resetting
        feedback_data = self.session.get("feedback_data", {})
        self.session.clear()

        # Restore feedback data so toast messages aren't lost
        if feedback_data:
            self.session["feedback_data"] = feedback_data

        # Initialize empty history
        self.session["history"] = []

        # Reinitialize adaptive learning if available
        if hasattr(self.exercise_service, 'adaptive') and self.exercise_service.adaptive:
            self.exercise_service.adaptive.initialize_performance_tracking(self.session)

        self.pick_new_question()

    def get_stats(self):
        """Get user statistics for display, including adaptive learning stats."""
        corr = self.session.get("correct_count", 0)
        inc = self.session.get("incorrect_count", 0)
        tot = corr + inc
        acc = (corr / tot * 100) if tot else 0

        stats = {
            "total": tot,
            "correct": corr,
            "incorrect": inc,
            "accuracy": acc,
            "current_streak": self.calculate_current_streak()
        }

        # Add adaptive learning stats if available
        if hasattr(self.exercise_service, 'adaptive') and self.exercise_service.adaptive:
            stats["weak_areas"] = self.exercise_service.adaptive.get_weak_areas(self.session)

        return stats

    def calculate_current_streak(self):
        """Calculate the current streak of correct answers."""
        streak = 0
        history = self.session.get("history", [])
        for entry in reversed(history):
            if entry["correct"]:
                streak += 1
            else:
                break
        return streak

#########################
# 7) UI Components
#########################

"""
Fixed UI Components for the Lithuanian Language Learning App
"""

class UIComponents:
    """Reusable UI components for the application."""

    @staticmethod
    def app_header() -> Container:
        """Create the app header with title, subtitle, and navigation."""
        # Create our custom brand element
        brand_element = DivLAligned(
            UkIcon("languages", height=30, width=30, cls="text-primary mr-3"),
            H3("Lithuanian", cls=(TextT.xl, TextT.bold, "text-primary")),
            P("Price Exercises", cls=TextT.muted),
            cls="items-center"
        )

        return Container(
            NavBar(
                Button("Home", cls=ButtonT.ghost, hx_get="/", hx_target="body"),
                Button("About", cls=ButtonT.ghost, hx_get="/about", hx_target="body"),
                Button("Stats", cls=ButtonT.ghost, hx_get="/stats", hx_target="body"),
                brand=brand_element,
                sticky=True,
                cls="py-2"
            ),
            cls="max-w-6xl mx-auto"
        )

    @staticmethod
    def question_form(question: str) -> Form:
        """Create the question form."""
        return Form(
            TextArea(
                id="user_answer",
                name="user_answer",
                placeholder="Type your answer in Lithuanian...",
                cls="w-full p-4 h-24 border rounded-md focus:ring-2 focus:ring-primary focus:border-primary transition-all"
            ),
            DivRAligned(
                Button(
                    UkIcon("send", cls="mr-2"),
                    "Submit Answer",
                    type="submit",
                    cls=(ButtonT.primary, "px-6 hover:bg-primary/90 transition-colors mt-4")
                )
            ),
            action="/answer",
            method="post",
            hx_boost="true",
            onkeydown="if(event.ctrlKey && event.key==='Enter') { this.submit(); }"
        )

    @staticmethod
    def question_card(question: str) -> Card:
        """Create exercise question card with answer form."""
        return Card(
            CardHeader(
                DivFullySpaced(
                    H3("Current Exercise", cls=TextT.lg),
                    Label("Practice", cls=LabelT.primary)
                )
            ),
            CardBody(
                Div(
                    P(question, cls="text-center text-xl font-medium p-4 rounded-lg mb-6"),
                    UIComponents.question_form(question),
                    cls="space-y-4"
                )
            ),
            cls="shadow-lg border-t-4 border-t-primary transition-all hover:shadow-xl"
        )

    @staticmethod
    def stat_metric(icon: str, value: str, label: str, color_class: str = "text-primary") -> Div:
        """Render a single stat metric."""
        return Div(
            DivCentered(
                UkIcon(icon, cls=f"{color_class} mb-1", height=24, width=24),
                H4(value, cls=(TextT.xl, TextT.bold, f"text-center text-2xl {color_class}")),
                P(label, cls=TextPresets.muted_sm)
            ),
            cls="p-3 rounded-md"
        )

    @staticmethod
    def accuracy_progress(accuracy: float) -> Div:
        """Render the accuracy progress bar."""
        progress_color = "bg-error" if accuracy < 60 else "bg-warning" if accuracy < 80 else "bg-success"

        return Div(
            P(f"Accuracy: {accuracy:.1f}%", cls=(TextT.bold, "mb-1")),
            Progress(
                value=int(min(100, accuracy)),
                max=100,
                cls=f"h-3 rounded-full {progress_color}"
            ),
            cls="mt-4 space-y-2"
        )

    @staticmethod
    def stats_card(stats: dict[str, Any]) -> Card:
        """Create statistics card with user progress."""
        metrics = [
            UIComponents.stat_metric("list", f"{stats['total']}", "Total", "text-primary"),
            UIComponents.stat_metric("check", f"{stats['correct']}", "Correct", "text-success"),
            UIComponents.stat_metric("x", f"{stats['incorrect']}", "Incorrect", "text-error"),
            UIComponents.stat_metric("flame", f"{stats['current_streak']}", "Streak", "text-warning")
        ]

        return Card(
            CardHeader(
                H3("Your Progress", cls=TextT.lg),
                Subtitle("Track your learning journey")
            ),
            CardBody(
                Grid(*metrics, cols=4, cols_sm=2, gap=4, cls="mb-4"),
                UIComponents.accuracy_progress(stats['accuracy']),
                Label(f"🔥 {stats['current_streak']}", cls=LabelT.warning) if stats['current_streak'] > 5 else "",
                cls="p-4"
            ),
            cls="shadow-lg border-t-4 border-t-secondary h-full"
        )

    @staticmethod
    def history_item(entry: dict, index: int, total: int) -> Div:
        """Render a single history item."""
        return Div(
            Div(
                UkIcon("check-circle" if entry["correct"] else "x-circle",
                    cls=f"{'text-success' if entry['correct'] else 'text-error'} mr-2"),
                Span(f"Q{total - index}", cls=(TextT.bold, "mr-2")),
                Span(entry['question'], cls=TextT.medium),
                cls="flex items-center"
            ),
            Div(
                P("Your answer:", cls=(TextT.gray, TextT.bold, "text-sm mt-2")),
                P(NotStr(entry['diff_user']), cls="ml-4"),
                P("Correct answer:", cls=(TextT.gray, TextT.bold, "text-sm mt-2")) if not entry["correct"] else "",
                P(NotStr(entry['diff_correct']), cls="ml-4") if not entry["correct"] else "",
                cls="ml-8 mt-1"
            ),
            cls=f"border-l-4 {'border-success' if entry['correct'] else 'border-error'} pl-4 py-2 mb-4"
        )

    @staticmethod
    def empty_history() -> DivCentered:
        """Render empty history state."""
        return DivCentered(
            UkIcon("history", height=40, width=40, cls="text-muted mb-2"),
            P("No history yet", cls=TextPresets.muted_lg),
            P("Your exercise history will appear here", cls=TextPresets.muted_sm),
            cls="py-16"
        )

    @staticmethod
    def history_card(history_items: list[dict[str, Any]]) -> Card:
        """Create history card showing past exercises as a timeline."""
        total_items = len(history_items)

        # Use the refactored components
        history_content = Div(
            *[UIComponents.history_item(entry, i, total_items)
            for i, entry in enumerate(reversed(history_items[-5:]))]  # Show only the most recent 5
        ) if history_items else UIComponents.empty_history()

        return Card(
            CardHeader(
                DivFullySpaced(
                    H3("Recent Exercises", cls=TextT.lg),
                    Button("View All", cls=ButtonT.ghost, hx_get="/stats", hx_target="body")
                ),
                Subtitle("Review your previous exercises")
            ),
            CardBody(
                history_content,
                cls="max-h-[400px] overflow-y-auto pr-2"
            ),
            cls="shadow-lg border-t-4 border-t-accent h-full"
        )

    @staticmethod
    def weak_area_item(area: dict) -> Li:
        """Render a single weak area item."""
        success_rate = area['success_rate'] * 100
        color_class = 'bg-error' if success_rate < 60 else 'bg-warning' if success_rate < 80 else 'bg-success'

        return Li(
            Div(
                P(f"{area['name'].replace('_', ' ').title()}", cls=TextT.medium),
                Progress(
                    value=int(success_rate),
                    max=100,
                    cls=f"h-2 rounded-full {color_class}"
                ),
                P(f"{success_rate:.1f}%", cls=TextPresets.muted_sm),
                cls="w-full"
            ),
            cls="mb-3"
        )

    @staticmethod
    def weak_area_section(category: str, areas: list[dict]) -> Div:
        """Render a section of weak areas for a category."""
        return Div(
            H4(category, cls=(TextT.bold, "mb-2")),
            Ul(*[UIComponents.weak_area_item(area) for area in areas], cls="space-y-2"),
            cls="mb-4"
        )

    @staticmethod
    def empty_weak_areas() -> DivCentered:
        """Render empty weak areas state."""
        return DivCentered(
            UkIcon("target", height=40, width=40, cls="text-muted mb-2"),
            P("Not enough data yet", cls=TextPresets.muted_lg),
            P("Complete more exercises to identify your weak areas", cls=TextPresets.muted_sm),
            cls="py-8"
        )

    @staticmethod
    def weak_areas_card(weak_areas: dict) -> Card:
        """Create a card showing the user's weak areas based on Thompson sampling."""
        if not weak_areas:
            return Card(
                CardHeader(
                    H3("Areas to Improve", cls=TextT.lg),
                    Subtitle("Focus on these areas")
                ),
                CardBody(UIComponents.empty_weak_areas()),
                cls="shadow-lg border-t-4 border-t-warning h-full"
            )

        weak_area_sections = [
            UIComponents.weak_area_section(category, areas)
            for category, areas in weak_areas.items()
        ]

        return Card(
            CardHeader(
                H3("Areas to Improve", cls=TextT.lg),
                Subtitle("Focus on these areas")
            ),
            CardBody(*weak_area_sections),
            cls="shadow-lg border-t-4 border-t-warning h-full"
        )

    @staticmethod
    def loading_indicator() -> Loading:
        """Create a loading indicator for HTMX requests."""
        return Loading(
            htmx_indicator=True,
            type=LoadingT.dots,
            cls="fixed top-0 left-0 w-full h-1 z-50"
        )

    @staticmethod
    def answer_feedback(is_correct: bool, user_answer: str, correct_answer: str) -> Toast:
        """Create feedback toast for answer submission."""
        return Toast(
            DivLAligned(
                UkIcon("check" if is_correct else "alert-triangle", cls=f"text-{'success' if is_correct else 'error'} mr-2"),
                Div(
                    P("Correct!" if is_correct else "Not quite right", cls=TextT.bold),
                    P(f"Your answer: {user_answer}", cls=TextT.sm),
                    P(f"Correct: {correct_answer}", cls=TextT.sm) if not is_correct else ""
                )
            ),
            cls=(ToastHT.end, ToastVT.bottom, "bg-base-100 shadow-lg text-base-content border-l-4 z-50" +
                (" border-success" if is_correct else " border-error")),
            duration=3000
        )

    @staticmethod
    def footer() -> Container:
        """Create the app footer."""
        return Div(
            DividerLine(),
            DivCentered(
                P("Lithuanian Price Exercise App © 2025", cls=TextPresets.muted_lg),
                DivLAligned(
                    UkIconLink("github", cls="text-muted hover:text-primary"),
                    UkIconLink("info", cls="text-muted hover:text-primary"),
                    cls="space-x-4"
                ),
                cls="py-6"
            ),
            cls="mt-8"
        )

    # Add a performance_by_category method for the stats page
    @staticmethod
    def performance_by_category(category_data: dict, title: str) -> Card:
        """Create a card showing performance by category."""
        items = []
        for key, stats in category_data.items():
            total = stats["correct"] + stats["incorrect"]
            success_rate = (stats["correct"] / total) * 100 if total > 0 else 0
            color_class = 'bg-error' if success_rate < 60 else 'bg-warning' if success_rate < 80 else 'bg-success'

            items.append(
                Div(
                    P(f"{key.replace('_', ' ').title()}", cls=TextT.medium),
                    Progress(
                        value=int(success_rate),
                        max=100,
                        cls=f"h-2 rounded-full {color_class}"
                    ),
                    P(f"{success_rate:.1f}% ({stats['correct']}/{total})", cls=TextPresets.muted_sm),
                    cls="mb-3"
                )
            )

        return Card(
            CardHeader(
                H3(title, cls=TextT.lg),
                Subtitle("Performance by category")
            ),
            CardBody(*items),
            cls="shadow-lg border-t-4 border-t-primary h-full"
        )

#########################
# 8) Thompson Sampling Testing
#########################

def test_thompson_sampling():
    """Test function to validate Thompson sampling behavior."""
    # Create a simulated session with biased performance
    simulated_session = {
        "performance": {
            "exercise_types": {
                "kokia": {"correct": 20, "incorrect": 5},  # Strong area
                "kiek": {"correct": 5, "incorrect": 20}    # Weak area
            },
            "number_patterns": {
                "single_digit": {"correct": 15, "incorrect": 5},  # Strong area
                "teens": {"correct": 10, "incorrect": 10},        # Medium area
                "decade": {"correct": 5, "incorrect": 15},        # Weak area
                "compound": {"correct": 5, "incorrect": 20}       # Very weak area
            },
            "grammatical_cases": {
                "nominative": {"correct": 20, "incorrect": 5},    # Strong area
                "accusative": {"correct": 5, "incorrect": 20}     # Weak area
            },
            "combined_arms": {},
            "total_exercises": 100
        }
    }

    # Create services
    adaptive_service = AdaptiveLearningService(exploration_rate=0)  # No exploration for testing
    db_service = DatabaseService()

    # Run multiple trials and count distribution of selected exercises
    trials = 1000
    selections = {
        "exercise_types": {},
        "number_patterns": {},
        "grammatical_cases": {}
    }

    for _ in range(trials):
        exercise = adaptive_service._thompson_sample_exercise(simulated_session, db_service)

        # Count exercise types
        ex_type = exercise["exercise_type"]
        selections["exercise_types"][ex_type] = selections["exercise_types"].get(ex_type, 0) + 1

        # Count number patterns
        num_pattern = exercise["number_pattern"]
        selections["number_patterns"][num_pattern] = selections["number_patterns"].get(num_pattern, 0) + 1

        # Count grammatical cases
        gram_case = exercise["grammatical_case"]
        selections["grammatical_cases"][gram_case] = selections["grammatical_cases"].get(gram_case, 0) + 1

    # Print results
    print("Thompson Sampling Test Results")
    print("=====================")

    for category, counts in selections.items():
        print(f"\n{category.replace('_', ' ').title()}:")
        total = sum(counts.values())
        for key, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total) * 100
            print(f"  {key}: {count} selections ({percentage:.1f}%)")

    # Validate the algorithm - weak areas should have higher selection rates
    if selections["exercise_types"].get("kiek", 0) > selections["exercise_types"].get("kokia", 0):
        print("\n✅ Thompson sampling correctly targets weak exercise type")
    else:
        print("\n❌ Thompson sampling failed to target weak exercise type")

    if selections["number_patterns"].get("compound", 0) > selections["number_patterns"].get("single_digit", 0):
        print("✅ Thompson sampling correctly targets weak number pattern")
    else:
        print("❌ Thompson sampling failed to target weak number pattern")

    if selections["grammatical_cases"].get("accusative", 0) > selections["grammatical_cases"].get("nominative", 0):
        print("✅ Thompson sampling correctly targets weak grammatical case")
    else:
        print("❌ Thompson sampling failed to target weak grammatical case")

    return selections

#########################
# 9) Application Setup
#########################

# Initialize services with adaptive learning
db_service = DatabaseService()
adaptive_service = AdaptiveLearningService(exploration_rate=0.2)
exercise_service = ExerciseService(db_service, adaptive_service)

def handle_not_found(req, exc):
    """Handle 404 errors."""
    return Titled("Not Found", P("The page you're looking for doesn't exist."))

def handle_server_error(req, exc):
    """Handle 500 errors."""
    return Titled("Server Error", P("Something went wrong. Please try again later."))

app, rt = fast_app(
    hdrs=Theme.green.headers(daisy=True),
    session_cookie="lithuanian_price_exercise2025-02-282",
    max_age=86400,
    title="",
    exception_handlers={
        404: handle_not_found,
        500: handle_server_error
    }
)

setup_toasts(app)  # Enable toasts for feedback

#########################
# 10) Routes
#########################

"""
This file contains the updated page routes with properly restored headers
"""

@rt("/")
def main_page(request):
    """Main page route with improved layout."""
    # Get session and setup
    sess, session_id = get_session(request)
    maybe_cleanup_sessions()
    session_manager = SessionManager(sess, exercise_service)
    session_manager.ensure_initialized()

    # Get stats and prepare components
    stats_data = session_manager.get_stats()

    # Quick stats cards
    metrics_row = Grid(
        UIComponents.stat_metric("list", str(stats_data['total']), "Total", "text-primary"),
        UIComponents.stat_metric("check", str(stats_data['correct']), "Correct", "text-success"),
        UIComponents.stat_metric("x", str(stats_data['incorrect']), "Incorrect", "text-error"),
        UIComponents.stat_metric("flame", str(stats_data['current_streak']), "Streak", "text-warning"),
        cols=4, cols_sm=2, gap=4,
        cls="mb-6"
    )

    # Question card
    question_card = UIComponents.question_card(sess["current_question"])

    # Weak areas card
    weak_areas_card = None
    if "weak_areas" in stats_data and stats_data["weak_areas"]:
        weak_areas_card = UIComponents.weak_areas_card(stats_data["weak_areas"])
    else:
        weak_areas_card = Card(
            CardHeader(
                H3("Areas to Improve", cls=TextT.lg),
                Subtitle("Focus on these areas")
            ),
            CardBody(
                DivCentered(
                    UkIcon("target", height=40, width=40, cls="text-muted mb-2"),
                    P("Complete more exercises", cls=TextPresets.muted_sm),
                    cls="py-8"
                )
            ),
            cls="shadow-lg border-t-4 border-t-warning h-full"
        )

    # History card
    history_card = UIComponents.history_card(sess.get("history", []))

    # Add feedback component if needed
    feedback_component = ""
    if sess.get("feedback_data", {}).get("show", False):
        feedback_data = sess["feedback_data"]
        # Use Modal for feedback instead of Toast
        feedback_component = Modal(
            ModalHeader(
                DivLAligned(
                    UkIcon("check-circle" if feedback_data["is_correct"] else "x-circle",
                        cls=f"{'text-success' if feedback_data['is_correct'] else 'text-error'} mr-2",
                        height=24, width=24),
                    H3("Correct!" if feedback_data["is_correct"] else "Incorrect",
                    cls=f"{'text-success' if feedback_data['is_correct'] else 'text-error'}")
                )
            ),
            ModalBody(
                Div(
                    Card(
                        CardBody(
                            P(feedback_data.get("question", sess.get("current_question", "")),
                            cls="mb-4 text-lg font-medium")
                        ),
                        cls="mb-4 bg-base-200"
                    ),

                    # Your answer section
                    Div(
                        P("Your answer:", cls=TextT.muted),
                        Card(
                            CardBody(
                                P(feedback_data["user_answer"],
                                cls=f"text-lg {'text-success font-medium' if feedback_data['is_correct'] else ''}")
                            ),
                            cls=f"{'border-success' if feedback_data['is_correct'] else 'border-error'} border"
                        ),
                        cls="mb-4"
                    ),

                    # Correct answer if wrong
                    Div(
                        P("Correct answer:", cls=TextT.muted),
                        Card(
                            CardBody(
                                P(feedback_data["correct_answer"], cls="text-lg text-success font-medium")
                            ),
                            cls="border-success border"
                        ),
                        cls="" if not feedback_data["is_correct"] else "hidden"
                    ),
                )
            ),
            ModalFooter(
                Button(
                    "Continue",
                    cls=ButtonT.primary,
                    onclick="document.getElementById('answer-feedback-modal').classList.remove('uk-open')"
                )
            ),
            id="answer-feedback-modal",
            cls="uk-open"
        )
        sess["feedback_data"]["show"] = False

    # Reset modal
    reset_modal = Modal(
        ModalHeader(H3("Reset Progress?")),
        ModalBody(P("This will clear all your history. Are you sure?")),
        ModalFooter(
            Button("Cancel", cls=ButtonT.ghost, data_uk_toggle="target: #reset-modal"),
            Button("Reset", cls=ButtonT.destructive, hx_post="/reset", hx_target="#main-content")
        ),
        id="reset-modal"
    )

    # Loading indicator
    loading = UIComponents.loading_indicator()

    # Main content layout
    main_content = Container(
        feedback_component,
        H2("Lithuanian Price Practice", cls=(TextT.xl, "mb-6")),
        metrics_row,
        Div(
            question_card,
            cls="mb-6"
        ),
        Grid(
            Div(weak_areas_card, cls="h-full col-span-1"),
            Div(history_card, cls="h-full col-span-1"),
            cols_md=2, cols_sm=1, gap=6
        ),
        Button(
            UkIcon("refresh-ccw", cls="mr-2"),
            "Reset Progress",
            cls=(ButtonT.destructive, "mt-6"),
            data_uk_toggle="target: #reset-modal"
        ),
        reset_modal,
        loading,
        UIComponents.footer(),  # Include the footer directly in the main content
        cls=(ContainerT.xl, "px-8 py-8"),
        id="main-content"
    )

    # RESTORED HEADER here
    page_container = Div(
        UIComponents.app_header(),
        main_content,
        cls="min-h-screen px-4"
    )

    # Save updated session and return response
    save_session(session_id, sess)
    return add_session_cookie(page_container, session_id)

@rt("/stats")
def stats_page(request):
    """Enhanced stats page with adaptive learning insights."""
    # Get session from database
    sess, session_id = get_session(request)

    session_manager = SessionManager(sess, exercise_service)
    stats = session_manager.get_stats()

    # Create basic stats card
    stats_card = UIComponents.stats_card(stats)

    # Get weak areas if available
    weak_areas_card = UIComponents.weak_areas_card(stats.get("weak_areas", {}))

    # Get performance by category if available
    performance_cards = []
    if "performance" in sess:
        perf = sess["performance"]

        # Exercise types performance
        if perf.get("exercise_types"):
            performance_cards.append(
                UIComponents.performance_by_category(perf["exercise_types"], "Exercise Types")
            )

        # Number patterns performance
        if perf.get("number_patterns"):
            performance_cards.append(
                UIComponents.performance_by_category(perf["number_patterns"], "Number Patterns")
            )

        # Grammatical cases performance
        if perf.get("grammatical_cases"):
            performance_cards.append(
                UIComponents.performance_by_category(perf["grammatical_cases"], "Grammatical Cases")
            )

    # Main content
    main_content = Container(
        H2("Your Statistics", cls=TextT.xl),
        P("Track your learning progress", cls=TextPresets.muted_lg),

        # Overall stats
        Div(stats_card, cls="mt-6"),

        # Weak areas section
        Div(weak_areas_card, cls="mt-6"),

        # Detailed performance section
        Div(
            H3("Detailed Performance", cls=(TextT.lg, "mt-8 mb-4")),
            Grid(*performance_cards, cols_md=1, cols_lg=2, cols_xl=3, gap=6)
            if performance_cards else
            DivCentered(
                UkIcon("info", height=40, width=40, cls="text-muted mb-2"),
                P("Complete more exercises to see detailed performance", cls=TextPresets.muted_lg),
                cls="py-8 bg-base-200 rounded-lg mt-4"
            ),
            cls="mt-6"
        ),

        Button(
            UkIcon("arrow-left", cls="mr-2"),
            "Back to Practice",
            cls=(ButtonT.primary, "mt-8"),
            hx_get="/",
            hx_target="body"
        ),

        UIComponents.footer(),  # Include footer here

        cls=(ContainerT.xl, "px-8 py-8"),
        id="main-content"
    )

    page_container = Div(
        UIComponents.app_header(),
        main_content,
        cls="min-h-screen px-4"
    )

    save_session(session_id, sess)
    return add_session_cookie(page_container, session_id)

@rt("/about")
def about_page(request):
    """About page with navigation back to main page."""
    # Get session from database if needed
    sess, session_id = get_session(request)

    main_content = Container(
        H2("About This App", cls=TextT.xl),
        P("Learn Lithuanian price expressions with this interactive tool!", cls=TextPresets.muted_lg),
        P("This application helps you practice how to express prices in Lithuanian through interactive exercises.",
          cls="mt-4"),
        P("The app features an adaptive learning system that uses Thompson sampling to target exercises to your weak areas.", cls="mt-4"),
        P("There are two types of exercises:", cls="mt-4"),
        Ul(
            Li("'Kokia kaina?' (What is the price?) - You need to express the given price in Lithuanian."),
            Li("'Kiek kainuoja?' (How much does it cost?) - You need to express how much a specific item costs.")
        ),
        P("Practice regularly to improve your Lithuanian language skills!", cls="mt-4"),
        Button(
            UkIcon("arrow-left", cls="mr-2"),
            "Back to Practice",
            cls=(ButtonT.primary, "mt-6"),
            hx_get="/",
            hx_target="body"
        ),

        UIComponents.footer(),  # Include footer here

        cls=(ContainerT.xl, "px-8 py-8"),
        id="main-content"
    )

    # RESTORED HEADER here
    page_container = Div(
        UIComponents.app_header(),
        main_content,
        cls="min-h-screen px-4"
    )

    save_session(session_id, sess)
    return add_session_cookie(page_container, session_id)

@rt("/reset")
def reset_progress(request):
    """Handle progress reset, also clears adaptive learning data."""
    # Get session from database
    sess, session_id = get_session(request)

    session_manager = SessionManager(sess, exercise_service)

    # Clear performance data if it exists
    if "performance" in sess:
        del sess["performance"]

    session_manager.reset()

    # Save the reset session
    save_session(session_id, sess)

    # Create redirect response with cookie
    response = RedirectResponse("/", status_code=303)
    return add_session_cookie(response, session_id)

@rt("/answer")
def submit_answer(request, user_answer: str = ""):
    """Handle answer submission with adaptive learning updates."""
    # Get session from database
    sess, session_id = get_session(request)

    # Create session manager
    session_manager = SessionManager(sess, exercise_service)

    # Ensure session is properly initialized
    if not all(k in sess for k in ["row_id", "exercise_type"]):
        session_manager.ensure_initialized()
        save_session(session_id, sess)
        response = RedirectResponse("/", status_code=303)
        return add_session_cookie(response, session_id)

    try:
        # Get the row from database
        row_id = sess["row_id"]
        row = db_service.get_row_by_number(row_id)

        # Process answer
        correct_answer = exercise_service.get_correct_answer(sess["exercise_type"], row)
        is_correct = exercise_service.check_answer(user_answer, correct_answer)

        # Store feedback for toast
        sess["feedback_data"] = {
            "is_correct": is_correct,
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "show": True
        }

        # Record answer and update adaptive learning model
        session_manager.record_answer(user_answer, correct_answer)

        # Save updated session back to database
        save_session(session_id, sess)

        # Create redirect response with cookie
        response = RedirectResponse("/", status_code=303)
        return add_session_cookie(response, session_id)

    except Exception as e:
        print(f"Error processing answer: {e}")
        session_manager.reset()
        save_session(session_id, sess)
        response = RedirectResponse("/", status_code=303)
        return add_session_cookie(response, session_id)

@rt("/admin/test-sampling")
def admin_test_sampling(request):
    """Admin route to test Thompson sampling."""
    # Get session if needed
    sess, session_id = get_session(request)

    results = test_thompson_sampling()

    # Create a visual representation of the test results
    result_sections = []

    for category, counts in results.items():
        section_items = []
        total = sum(counts.values())

        for key, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total) * 100
            section_items.append(
                Div(
                    DivFullySpaced(
                        P(key.replace('_', ' ').title(), cls=TextT.medium),
                        P(f"{count} ({percentage:.1f}%)", cls=TextPresets.muted_sm)
                    ),
                    Progress(
                        value=int(percentage),
                        max=100,
                        cls="h-2 rounded-full bg-primary"
                    ),
                    cls="mb-4"
                )
            )

        result_sections.append(
            Card(
                CardHeader(
                    H3(category.replace('_', ' ').title(), cls=TextT.lg),
                    Subtitle(f"Distribution of selections over {total} trials")
                ),
                CardBody(*section_items),
                cls="mt-6"
            )
        )

    response = Container(
        UIComponents.app_header(),
        Container(
            H2("Thompson Sampling Test Results", cls=TextT.xl),
            P("Validation of the adaptive algorithm's behavior", cls=TextPresets.muted_lg),

            Alert(
                DivLAligned(
                    UkIcon("info", cls="mr-2"),
                    Div(
                        P("This test simulates a user who performs better on:", cls=TextT.bold),
                        Ul(
                            Li("'Kokia' exercise type"),
                            Li("Single digit numbers"),
                            Li("Nominative case"),
                            cls="list-disc ml-6 mt-2"
                        ),
                        P("The algorithm should preferentially select the opposite categories where the user is weaker.", cls="mt-2"),
                    )
                ),
                cls=(AlertT.info, "mt-6")
            ),

            *result_sections,

            Button(
                UkIcon("arrow-left", cls="mr-2"),
                "Back to Practice",
                cls=(ButtonT.primary, "mt-8"),
                hx_get="/",
                hx_target="body"
            ),
            cls="max-w-5xl mx-auto py-6",
            id="main-content"
        ),
        UIComponents.footer(),
        cls="min-h-screen bg-gradient-to-b from-base-100 to-base-200"
    )

    return add_session_cookie(response, session_id)

#########################
# 11) Application Entry Point
#########################

if __name__ == "__main__":
    serve()
