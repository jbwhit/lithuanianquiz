"""
Lithuanian Price Exercise App
A language learning tool for practicing Lithuanian price expressions with beautiful UI.
"""
import html
import random
from difflib import SequenceMatcher
from typing import Any, Literal

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
# 4) Exercise Logic
#########################

class ExerciseService:
    """Handles exercise generation and answer validation."""

    def __init__(self, db_service: DatabaseService):
        """Initialize with database service."""
        self.db = db_service

    def generate_exercise(self) -> tuple[ExerciseType, str, str | None, dict[str, Any]]:
        """Generate a random exercise."""
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
# 5) Session Management
#########################

class SessionManager:
    """Manages session state for the application."""

    def __init__(self, session: dict[str, Any], exercise_service: ExerciseService):
        """Initialize with session object and exercise service."""
        self.session = session
        self.exercise_service = exercise_service

    def ensure_initialized(self) -> None:
        """Initialize session with default values if needed."""
        if "current_question" not in self.session:
            self.pick_new_question()
        if "history" not in self.session:
            self.session["history"] = []
        if "correct_count" not in self.session:
            self.session["correct_count"] = 0
        if "incorrect_count" not in self.session:
            self.session["incorrect_count"] = 0

    def pick_new_question(self) -> None:
        """Generate and store a new question in the session."""
        ex_type, price, item, row = self.exercise_service.generate_exercise()
        self.session["exercise_type"] = ex_type
        self.session["price"] = price
        self.session["item"] = item
        self.session["row_id"] = row["number"]
        self.session["current_question"] = self.exercise_service.format_question(ex_type, price, item)

    def record_answer(self, user_answer: str, correct_answer: str) -> None:
        """Record user answer and update statistics."""
        user_str = user_answer.strip()
        correct_str = correct_answer.strip()
        is_correct = self.exercise_service.check_answer(user_str, correct_str)

        # Generate diffs for proper display
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

        if is_correct:
            self.session["correct_count"] = self.session.get("correct_count", 0) + 1
        else:
            self.session["incorrect_count"] = self.session.get("incorrect_count", 0) + 1

        history_entry = {
            "question": self.session["current_question"],
            "answer": user_str,
            "correct": is_correct,
            "diff_user": diff_user,
            "diff_correct": diff_correct,
            "true_answer": correct_str
        }
        self.session["history"].append(history_entry)
        self.pick_new_question()

    def reset(self) -> None:
        """Clear session and initialize a new question."""
        self.session.clear()
        self.pick_new_question()

    def get_stats(self) -> dict[str, Any]:
        """Get user statistics for display."""
        corr = self.session.get("correct_count", 0)
        inc = self.session.get("incorrect_count", 0)
        tot = corr + inc
        acc = (corr / tot * 100) if tot else 0
        return {
            "total": tot,
            "correct": corr,
            "incorrect": inc,
            "accuracy": acc,
            "current_streak": self.calculate_current_streak()
        }

    def calculate_current_streak(self) -> int:
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
# 6) UI Components
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

#########################
# 7) Application Setup
#########################

db_service = DatabaseService()
exercise_service = ExerciseService(db_service)

app, rt = fast_app(
    hdrs=Theme.green.headers(daisy=True),
    session_cookie="lithuanian_price_exercise2",
    title=""  # Set empty title to remove the "Title" text
)
setup_toasts(app)  # Enable toasts for feedback

#########################
# 8) Routes
#########################

@rt("/")
def main_page(sess):
    """Main page route - display exercise interface."""
    session_manager = SessionManager(sess, exercise_service)
    session_manager.ensure_initialized()

    header = UIComponents.app_header()
    question = UIComponents.question_card(sess["current_question"])
    stats = UIComponents.stats_card(session_manager.get_stats())
    history = UIComponents.history_card(sess["history"])  # No longer reversing the history here
    loading = UIComponents.loading_indicator()
    footer = UIComponents.footer()

    feedback_component = ""
    if sess.get("feedback_data", {}).get("show", False):
        feedback_data = sess["feedback_data"]
        feedback_component = UIComponents.answer_feedback(
            feedback_data["is_correct"],
            feedback_data["user_answer"],
            feedback_data["correct_answer"]
        )
        sess["feedback_data"]["show"] = False

    # Return the entire page structure, not just the main content
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
    """Handle progress reset."""
    session_manager = SessionManager(sess, exercise_service)
    session_manager.reset()
    return RedirectResponse("/", status_code=303)

@rt("/answer")
def submit_answer(sess, user_answer: str):
    """Handle answer submission."""
    try:
        session_manager = SessionManager(sess, exercise_service)
        row_id = sess["row_id"]
        row = db_service.get_row_by_number(row_id)
        correct_answer = exercise_service.get_correct_answer(sess["exercise_type"], row)
        is_correct = exercise_service.check_answer(user_answer, correct_answer)
        sess["feedback_data"] = {
            "is_correct": is_correct,
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "show": True
        }
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
    """Stats page with navigation back to main page."""
    session_manager = SessionManager(sess, exercise_service)
    stats_card = UIComponents.stats_card(session_manager.get_stats())

    return Container(
        H2("Your Statistics", cls=TextT.xl),
        P("Track your learning progress", cls=TextPresets.muted_lg),
        Div(stats_card, cls="mt-6"),
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

#########################
# 9) Application Entry Point
#########################

if __name__ == "__main__":
    serve()
