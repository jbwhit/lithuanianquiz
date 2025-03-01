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

    @property
    def rows(self) -> list[dict[str, Any]]:
        """Get all number rows from database with caching."""
        if self._rows_cache is None:
            self._rows_cache = list(self.numbers.rows)
        return self._rows_cache

    def get_row_by_number(self, number: int) -> dict[str, Any]:
        """Get a specific row by its number value."""
        for row in self.rows:
            if row["number"] == number:
                return row
        raise ValueError(f"No row found for number: {number}")


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
        if "current_question" not in self.session:
            self.pick_new_question()
        if "history" not in self.session:
            self.session["history"] = []
        if "correct_count" not in self.session:
            self.session["correct_count"] = 0
        if "incorrect_count" not in self.session:
            self.session["incorrect_count"] = 0

    def pick_new_question(self):
        """Generate and store a new question in the session using adaptive learning."""
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

    def record_answer(self, user_answer, correct_answer):
        """Record user answer and update adaptive learning model."""
        # Existing answer recording logic
        user_str = user_answer.strip()
        correct_str = correct_answer.strip()
        is_correct = self.exercise_service.check_answer(user_str, correct_str)

        # Generate diffs for display (existing code)
        if is_correct:
            diff_user = f"<span class='text-success font-bold'>{html.escape(user_str)}</span>"
            diff_correct = html.escape(correct_str)
        else:
            # Fix capitalization issues in the difference highlighting
            user_esc = html.escape(user_str.lower())
            corr_esc = html.escape(correct_str.lower())

            sm = SequenceMatcher(None, user_esc, corr_esc)
            out_user, out_corr = [], []

            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                seg_u = html.escape(user_str[i1:i2])  # Use original case for display
                seg_c = html.escape(correct_str[j1:j2])  # Use original case for display

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

            diff_user = "".join(out_user)
            diff_correct = "".join(out_corr)

        # Update counters
        if is_correct:
            self.session["correct_count"] = self.session.get("correct_count", 0) + 1
        else:
            self.session["incorrect_count"] = self.session.get("incorrect_count", 0) + 1

        # Add to history
        history_entry = {
            "question": self.session["current_question"],
            "answer": user_str,
            "correct": is_correct,
            "diff_user": diff_user,
            "diff_correct": diff_correct,
            "true_answer": correct_str
        }
        self.session["history"].append(history_entry)

        # Update adaptive learning with this attempt
        if hasattr(self.exercise_service, 'adaptive') and self.exercise_service.adaptive:
            exercise_info = {
                "exercise_type": self.session["exercise_type"],
                "grammatical_case": self.session.get("grammatical_case"),
                "number_pattern": self.session.get("number_pattern"),
                "row_id": self.session["row_id"]
            }
            self.exercise_service.adaptive.update_performance(
                self.session, exercise_info, is_correct
            )

        # Pick a new question
        self.pick_new_question()

    def reset(self):
        """Clear session and initialize a new question."""
        self.session.clear()

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

class UIComponents:
    """Reusable UI components for the application."""

    @staticmethod
    def app_header() -> Container:
        """Create the app header with title, subtitle, and navigation."""
        # Create our custom brand element to override the default "Title"
        brand_element = DivLAligned(
            H3("Lithuanian Price Exercises", cls=(TextT.xl, TextT.bold, "text-primary")),
            Div(UkIcon("languages", height=40, width=40, cls="text-primary"), cls="bg-primary/10 p-2 rounded-full"),
            cls="items-center space-x-4"
        )

        return Container(
            NavBar(
                Button("Home", cls=ButtonT.ghost, hx_get="/", hx_target="body"),
                Button("About", cls=ButtonT.ghost, hx_get="/about", hx_target="body"),
                Button("Stats", cls=ButtonT.ghost, hx_get="/stats", hx_target="body"),
                # Explicitly set the brand parameter to override the default "Title"
                brand=brand_element,
                sticky=True,
                cls="bg-base-200 shadow-md py-2"
            ),
            cls="max-w-5xl mx-auto py-4"
        )

    @staticmethod
    def question_card(question: str) -> Card:
        """Create exercise question card with answer form."""
        return Card(
            CardHeader(
                H3("Current Exercise", cls=TextT.lg),
                Subtitle("Practice your Lithuanian price expressions")
            ),
            CardBody(
                Div(
                    P(question, cls=(TextT.lead, "mb-6 text-xl font-medium")),
                    Form(
                        TextArea(
                            id="user_answer",
                            placeholder="Type your answer in Lithuanian...",
                            cls="w-full p-4 h-24 border rounded-md focus:ring-2 focus:ring-primary focus:border-primary transition-all bg-base-100"
                        ),
                        DivFullySpaced(
                            Div(),  # Empty div to maintain spacing
                            Button(
                                UkIcon("send", cls="mr-2"),
                                "Submit Answer",
                                cls=(ButtonT.primary, "px-6 hover:bg-primary/90 transition-colors")
                            ),
                            cls="mt-4"
                        ),
                        action="/answer",
                        method="post",
                        onkeydown="if(event.ctrlKey && event.key==='Enter') { this.submit(); }"
                    ),
                    cls="space-y-4"
                )
            ),
            cls=(CardT.hover, "shadow-lg border-t-4 border-t-primary transition-all hover:shadow-xl")
        )

    @staticmethod
    def stats_card(stats: dict[str, Any]) -> Card:
        """Create statistics card with user progress."""
        accuracy = stats['accuracy']
        progress_color = "bg-error" if accuracy < 60 else "bg-warning" if accuracy < 80 else "bg-success"

        return Card(
            CardHeader(
                H3("Your Progress", cls=TextT.lg),
                Subtitle("Track your learning journey")
            ),
            CardBody(
                Grid(
                    Card(
                        CardBody(
                            DivCentered(
                                UkIcon("list", cls="text-primary mb-2", height=24, width=24),
                                H4(f"{stats['total']}", cls=(TextT.xl, TextT.bold, "text-center text-2xl")),
                                P("Total Exercises", cls=TextPresets.muted_sm)
                            )
                        ),
                        cls="shadow-sm"
                    ),
                    Card(
                        CardBody(
                            DivCentered(
                                UkIcon("check", cls="text-success mb-2", height=24, width=24),
                                H4(f"{stats['correct']}", cls=(TextT.xl, TextT.bold, "text-center text-2xl text-success")),
                                P("Correct", cls=TextPresets.muted_sm)
                            )
                        ),
                        cls="shadow-sm"
                    ),
                    Card(
                        CardBody(
                            DivCentered(
                                UkIcon("x", cls="text-error mb-2", height=24, width=24),
                                H4(f"{stats['incorrect']}", cls=(TextT.xl, TextT.bold, "text-center text-2xl text-error")),
                                P("Incorrect", cls=TextPresets.muted_sm)
                            )
                        ),
                        cls="shadow-sm"
                    ),
                    Card(
                        CardBody(
                            DivCentered(
                                UkIcon("flame", cls="text-warning mb-2", height=24, width=24),
                                H4(f"{stats['current_streak']}", cls=(TextT.xl, TextT.bold, "text-center text-2xl text-warning")),
                                P("Streak", cls=TextPresets.muted_sm)
                            )
                        ),
                        cls="shadow-sm"
                    ),
                    cols=4, cols_sm=2, gap=4, cls="mb-4"
                ),
                Div(
                    P(f"Accuracy: {stats['accuracy']:.1f}%", cls=(TextT.bold, "mb-1")),
                    Progress(
                        value=int(min(100, accuracy)),
                        max=100,
                        cls=f"h-3 rounded-full {progress_color}"
                    ),
                    Label(f"🔥 {stats['current_streak']}", cls=LabelT.warning) if stats['current_streak'] > 5 else "",
                    cls="mt-4 space-y-2"
                ),
                Modal(
                    ModalHeader(H3("Reset Progress?")),
                    ModalBody(P("This will clear all your history. Are you sure?")),
                    ModalFooter(
                        Button("Cancel", cls=ButtonT.ghost, data_uk_toggle="target: #reset-modal"),
                        Button("Reset", cls=ButtonT.destructive, hx_post="/reset", hx_target="#main-content")
                    ),
                    id="reset-modal"
                ),
                Button(
                    UkIcon("refresh", cls="mr-2"),
                    "Reset Progress",
                    cls=(ButtonT.destructive, "mt-4"),
                    data_uk_toggle="target: #reset-modal"
                )
            ),
            cls=(CardT.hover, "shadow-lg border-t-4 border-t-secondary h-full")
        )

    @staticmethod
    def history_card(history_items: list[dict[str, Any]]) -> Card:
        """Create history card showing past exercises as a timeline."""
        total_items = len(history_items)

        # Create the most recent items first (reversed order)
        history_items_reversed = list(reversed(history_items))

        history_content = Div(
            *[Div(
                Div(
                    UkIcon("check-circle" if entry["correct"] else "x-circle",
                          cls=f"{'text-success' if entry['correct'] else 'text-error'} mr-2"),
                    Span(f"Q{total_items - i}", cls=(TextT.bold, "mr-2")),
                    Span(entry['question'], cls=TextT.medium),
                    cls="flex items-center"
                ),
                Div(
                    P("Your answer:", cls=(TextT.gray, TextT.bold, "text-sm mt-2")),
                    P(NotStr(entry['diff_user']), cls="ml-4"),
                    P("Correct answer:", cls=(TextT.gray, TextT.bold, "text-sm mt-2")),
                    P(NotStr(entry['diff_correct']), cls="ml-4"),
                    cls="ml-8 mt-1"
                ),
                cls=f"border-l-4 {'border-success' if entry['correct'] else 'border-error'} pl-4 py-2 mb-6"
            ) for i, entry in enumerate(history_items_reversed)]
        ) if history_items else DivCentered(
            UkIcon("history", height=40, width=40, cls="text-muted mb-2"),
            P("No history yet", cls=TextPresets.muted_lg),
            P("Your exercise history will appear here", cls=TextPresets.muted_sm),
            cls="py-16"
        )

        return Card(
            CardHeader(
                DivFullySpaced(
                    H3("Exercise History", cls=TextT.lg),
                    Label(f"{total_items}", cls=(LabelT.primary, "px-3 py-1"))
                ),
                Subtitle("Review your previous exercises")
            ),
            CardBody(
                Div(
                    history_content,
                    cls="max-h-[400px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-primary scrollbar-track-base-200"
                )
            ),
            cls=(CardT.hover, "shadow-lg border-t-4 border-t-accent")
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
    def loading_indicator() -> Loading:
        """Create a loading indicator for HTMX requests."""
        return Loading(
            htmx_indicator=True,
            type=LoadingT.dots,
            cls="fixed top-4 right-4 z-50"
        )

    @staticmethod
    def footer() -> Container:
        """Create the app footer."""
        return Container(
            DividerSplit(cls="mt-8"),
            DivCentered(
                P("Lithuanian Price Exercise App © 2025", cls=TextPresets.muted_lg),
                DivLAligned(
                    UkIconLink("github", cls="text-muted hover:text-primary"),
                    UkIconLink("info", cls="text-muted hover:text-primary"),
                    cls="space-x-4"
                ),
                cls="py-6"
            ),
            cls="max-w-5xl mx-auto shadow-sm"
        )

    @staticmethod
    def weak_areas_card(weak_areas):
        """Create a card showing the user's weak areas based on Thompson sampling."""
        if not weak_areas:
            return Card(
                CardHeader(
                    H3("Weak Areas", cls=TextT.lg),
                    Subtitle("Areas that need more practice")
                ),
                CardBody(
                    DivCentered(
                        UkIcon("target", height=40, width=40, cls="text-muted mb-2"),
                        P("Not enough data yet", cls=TextPresets.muted_lg),
                        P("Complete more exercises to identify your weak areas", cls=TextPresets.muted_sm),
                        cls="py-8"
                    )
                ),
                cls=(CardT.hover, "shadow-lg border-t-4 border-t-warning h-full")
            )

        weak_area_sections = []
        for category, areas in weak_areas.items():
            area_items = []
            for area in areas:
                # Calculate color based on success rate
                success_rate = area['success_rate'] * 100
                color_class = 'bg-error' if success_rate < 60 else 'bg-warning' if success_rate < 80 else 'bg-success'

                area_items.append(
                    Li(
                        Div(
                            P(f"{area['name'].replace('_', ' ').title()}", cls=TextT.medium),
                            Progress(
                                value=int(success_rate),
                                max=100,
                                cls=f"h-2 rounded-full {color_class}"
                            ),
                            P(f"{success_rate:.1f}% success rate", cls=TextPresets.muted_sm),
                            cls="w-full"
                        ),
                        cls="mb-3"
                    )
                )

            section = Div(
                H4(category, cls=(TextT.bold, "mb-2")),
                Ul(*area_items, cls="space-y-2"),
                cls="mb-4"
            )
            weak_area_sections.append(section)

        return Card(
            CardHeader(
                H3("Weak Areas", cls=TextT.lg),
                Subtitle("Areas that need more practice")
            ),
            CardBody(*weak_area_sections),
            cls=(CardT.hover, "shadow-lg border-t-4 border-t-warning h-full")
        )

    @staticmethod
    def performance_by_category(category_data, title):
        """Create a card showing performance by category."""
        if not category_data:
            return Card(
                CardHeader(
                    H3(title, cls=TextT.lg),
                    Subtitle(f"Your performance by {title.lower()}")
                ),
                CardBody(
                    DivCentered(
                        UkIcon("bar-chart", height=40, width=40, cls="text-muted mb-2"),
                        P("No data available", cls=TextPresets.muted_lg),
                        cls="py-8"
                    )
                ),
                cls=(CardT.hover, "shadow-lg border-t-4 border-t-primary h-full")
            )

        # Calculate success rates
        success_rates = []
        for key, stats in category_data.items():
            total = stats["correct"] + stats["incorrect"]
            if total > 1:  # Only include categories with actual data
                rate = stats["correct"] / total
                success_rates.append({
                    "name": key.replace('_', ' ').title(),
                    "rate": rate,
                    "correct": stats["correct"],
                    "total": total
                })

        # Sort by success rate ascending (worst first)
        success_rates.sort(key=lambda x: x["rate"])

        category_items = []
        for item in success_rates:
            # Calculate color based on success rate
            rate_percent = item["rate"] * 100
            color_class = 'bg-error' if rate_percent < 60 else 'bg-warning' if rate_percent < 80 else 'bg-success'

            category_items.append(
                Div(
                    DivFullySpaced(
                        P(item["name"], cls=TextT.medium),
                        P(f"{item['correct']}/{item['total']}", cls=TextPresets.muted_sm)
                    ),
                    Progress(
                        value=int(rate_percent),
                        max=100,
                        cls=f"h-2 rounded-full {color_class}"
                    ),
                    cls="mb-4"
                )
            )

        return Card(
            CardHeader(
                H3(title, cls=TextT.lg),
                Subtitle(f"Your performance by {title.lower()}")
            ),
            CardBody(*category_items),
            cls=(CardT.hover, "shadow-lg border-t-4 border-t-primary h-full")
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

app, rt = fast_app(
    hdrs=Theme.green.headers(daisy=True),
    session_cookie="lithuanian_price_exercise2",
    title=""  # Set empty title to remove the "Title" text
)
setup_toasts(app)  # Enable toasts for feedback

#########################
# 10) Routes
#########################

@rt("/")
def main_page(sess):
    """Main page route - display exercise interface with adaptive learning."""
    session_manager = SessionManager(sess, exercise_service)
    session_manager.ensure_initialized()

    header = UIComponents.app_header()
    question = UIComponents.question_card(sess["current_question"])
    stats = UIComponents.stats_card(session_manager.get_stats())
    history = UIComponents.history_card(sess["history"])
    loading = UIComponents.loading_indicator()
    footer = UIComponents.footer()

    # Add adaptive feedback toast if available
    feedback_component = ""
    if sess.get("feedback_data", {}).get("show", False):
        feedback_data = sess["feedback_data"]
        feedback_component = UIComponents.answer_feedback(
            feedback_data["is_correct"],
            feedback_data["user_answer"],
            feedback_data["correct_answer"]
        )
        sess["feedback_data"]["show"] = False

    # Return the entire page structure
    return Div(
        header,
        Container(
            feedback_component,
            Grid(
                Div(question, cls="col-span-2"),
                Div(stats, cls="col-span-1"),
                cols_md=3, cols_sm=1, gap=6, cls="items-stretch"
            ),
            Div(history, cls="mt-8"),
            loading,
            cls=(ContainerT.lg, "px-6 py-8"),
            id="main-content"
        ),
        footer,
        cls="min-h-screen bg-gradient-to-b from-base-100 to-base-200"
    )

@rt("/reset")
def reset_progress(sess):
    """Handle progress reset, also clears adaptive learning data."""
    session_manager = SessionManager(sess, exercise_service)

    # Clear performance data if it exists
    if "performance" in sess:
        del sess["performance"]

    session_manager.reset()
    return RedirectResponse("/", status_code=303)

@rt("/answer")
def submit_answer(sess, user_answer: str):
    """Handle answer submission with adaptive learning updates."""
    try:
        session_manager = SessionManager(sess, exercise_service)
        row_id = sess["row_id"]
        row = db_service.get_row_by_number(row_id)
        correct_answer = exercise_service.get_correct_answer(sess["exercise_type"], row)
        is_correct = exercise_service.check_answer(user_answer, correct_answer)

        # Store feedback data for toast
        sess["feedback_data"] = {
            "is_correct": is_correct,
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "show": True
        }

        # Record answer (will also update adaptive learning model)
        session_manager.record_answer(user_answer, correct_answer)

        return RedirectResponse("/", status_code=303)
    except Exception as e:
        print(f"Error processing answer: {e}")
        return RedirectResponse("/", status_code=303)

@rt("/about")
def about_page():
    """About page with navigation back to main page."""
    return Container(
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
        cls="max-w-5xl mx-auto py-6",
        id="main-content"
    )

@rt("/stats")
def stats_page(sess):
    """Enhanced stats page with adaptive learning insights."""
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

    return Container(
        UIComponents.app_header(),
        Container(
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
            cls="max-w-5xl mx-auto py-6",
            id="main-content"
        ),
        UIComponents.footer(),
        cls="min-h-screen bg-gradient-to-b from-base-100 to-base-200"
    )

@rt("/admin/test-sampling")
def admin_test_sampling():
    """Admin route to test Thompson sampling."""
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

    return Container(
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

#########################
# 11) Application Entry Point
#########################

if __name__ == "__main__":
    serve()
