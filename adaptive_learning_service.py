import random

import numpy as np


class AdaptiveLearningService:
    """Implements Thompson sampling for adaptive learning engine."""

    def __init__(self, exploration_rate=0.2):
        """Initialize with exploration/exploitation balance.

        Args:
            exploration_rate: Probability of random exploration (default 20%)
        """
        self.exploration_rate = exploration_rate  # 20% random, 80% targeted
        self.adaptation_threshold = 10  # Start meaningful adaptation after 10 exercises

    def initialize_performance_tracking(self, session):
        """Set up initial performance tracking with 1 incorrect answer assumption."""
        if "performance" not in session:
            session["performance"] = {
                # Track by exercise type
                "exercise_types": {ex_type: {"correct": 0, "incorrect": 1}
                                  for ex_type in ["kokia", "kiek"]},

                # Track by number pattern - will be filled as exercises are encountered
                "number_patterns": {},

                # Track by grammatical case - will be filled as exercises are encountered
                "grammatical_cases": {},

                # Combined tracking - will be filled as exercises are encountered
                "combined_arms": {},

                # Total exercises attempted
                "total_exercises": 0
            }

    def update_performance(self, session, exercise_info, is_correct):
        """Update performance tracking after an exercise attempt.

        Args:
            session: User session data
            exercise_info: Information about the current exercise
            is_correct: Whether the user answered correctly
        """
        if "performance" not in session:
            self.initialize_performance_tracking(session)

        perf = session["performance"]
        perf["total_exercises"] += 1

        # Update exercise type tracking
        ex_type = exercise_info["exercise_type"]
        self._update_arm(perf["exercise_types"], ex_type, is_correct)

        # Update number pattern tracking
        number_pattern = exercise_info.get("number_pattern")
        if number_pattern:
            self._update_arm(perf["number_patterns"], number_pattern, is_correct)

        # Update grammatical case tracking
        grammatical_case = exercise_info.get("grammatical_case")
        if grammatical_case:
            self._update_arm(perf["grammatical_cases"], grammatical_case, is_correct)

        # Update combined tracking for more specific targeting
        if number_pattern and grammatical_case:
            combined_key = f"{ex_type}_{number_pattern}_{grammatical_case}"
            self._update_arm(perf["combined_arms"], combined_key, is_correct)

    def _update_arm(self, category_dict, key, is_correct):
        """Update a specific arm in the performance tracking.

        Args:
            category_dict: Dictionary of performance for a category
            key: The specific arm to update
            is_correct: Whether the answer was correct
        """
        if key not in category_dict:
            category_dict[key] = {"correct": 0, "incorrect": 1}  # Start with 1 incorrect

        if is_correct:
            category_dict[key]["correct"] += 1
        else:
            category_dict[key]["incorrect"] += 1

    def select_exercise(self, session, db_service):
        """Select the next exercise using Thompson sampling.

        Args:
            session: User session data
            db_service: Database service for retrieving exercise data

        Returns:
            Dictionary with exercise details
        """
        if "performance" not in session:
            self.initialize_performance_tracking(session)

        perf = session["performance"]

        # Use random exploration with probability exploration_rate or if under threshold
        if random.random() < self.exploration_rate or perf["total_exercises"] < self.adaptation_threshold:
            # Explore: return a random exercise
            return self._generate_random_exercise(db_service)

        # Exploit: use Thompson sampling to select from weak areas
        return self._thompson_sample_exercise(session, db_service)

    def _generate_random_exercise(self, db_service):
        """Generate a completely random exercise."""
        row = random.choice(db_service.rows)
        exercise_type = random.choice(["kokia", "kiek"])
        item = random.choice(["knyga", "puodelis", "marškinėliai", "žurnalas", "kepurė"]) if exercise_type == "kiek" else None

        # Determine grammatical case and number pattern
        grammatical_case = "accusative" if exercise_type == "kiek" else "nominative"
        number_pattern = self._determine_number_pattern(row["number"])

        return {
            "exercise_type": exercise_type,
            "price": f"€{row['number']}",
            "item": item,
            "row": row,
            "grammatical_case": grammatical_case,
            "number_pattern": number_pattern
        }

    def _thompson_sample_exercise(self, session, db_service):
        """Use Thompson sampling to select exercise targeting weak areas."""
        perf = session["performance"]

        # Step 1: Sample from distributions to find weakest exercise type
        selected_ex_type = self._sample_weakest_exercise_type(perf)

        # Step 2: Find suitable number pattern and grammatical case
        selected_number_pattern, selected_grammatical_case = self._sample_parameters(
            perf, selected_ex_type, db_service
        )

        # Step 3: Find a row matching these criteria
        row = self._find_matching_row(db_service, selected_number_pattern)

        # If no matching row was found, _find_matching_row returns None
        if row is None:
            return self._generate_random_exercise(db_service)

        # Create the exercise
        item = None
        if selected_ex_type == "kiek":
            item = random.choice(["knyga", "puodelis", "marškinėliai", "žurnalas", "kepurė"])

        return {
            "exercise_type": selected_ex_type,
            "price": f"€{row['number']}",
            "item": item,
            "row": row,
            "grammatical_case": selected_grammatical_case,
            "number_pattern": selected_number_pattern
        }

    def _sample_weakest_exercise_type(self, perf):
        """Sample to find the weakest exercise type."""
        ex_type_samples = {}
        for ex_type, stats in perf["exercise_types"].items():
            alpha = stats["correct"] + 1
            beta_val = stats["incorrect"] + 1
            ex_type_samples[ex_type] = np.random.beta(alpha, beta_val)

        # Find the exercise type with the lowest sample (weakest performance)
        return min(ex_type_samples, key=ex_type_samples.get)

    def _sample_parameters(self, perf, selected_ex_type, db_service):
        """Sample to find the weakest number pattern and grammatical case."""
        # First see if we have any combined arms for this exercise type
        relevant_combined_arms = {
            k: v for k, v in perf["combined_arms"].items()
            if k.startswith(f"{selected_ex_type}_")
        }

        if relevant_combined_arms:
            # Use combined sampling when we have data
            return self._sample_from_combined_arms(relevant_combined_arms)
        else:
            # Fall back to separate sampling
            return self._sample_separate_parameters(perf, selected_ex_type, db_service)

    def _sample_from_combined_arms(self, relevant_combined_arms):
        """Sample from combined arms to find weakest parameters."""
        combined_samples = {}
        for arm, stats in relevant_combined_arms.items():
            alpha = stats["correct"] + 1
            beta_val = stats["incorrect"] + 1
            combined_samples[arm] = np.random.beta(alpha, beta_val)

        # Find the weakest combined arm
        selected_combined = min(combined_samples, key=combined_samples.get)
        parts = selected_combined.split('_', 2)

        selected_number_pattern = parts[1] if len(parts) > 1 else None
        selected_grammatical_case = parts[2] if len(parts) > 2 else None

        return selected_number_pattern, selected_grammatical_case

    def _sample_separate_parameters(self, perf, selected_ex_type, db_service):
        """Sample number pattern and grammatical case separately."""
        # Sample for number pattern
        selected_number_pattern = self._sample_number_pattern(perf, db_service)

        # Default and potentially override grammatical case
        selected_grammatical_case = "accusative" if selected_ex_type == "kiek" else "nominative"

        # Sample for grammatical case if we have data
        gram_cases = perf.get("grammatical_cases", {})
        if gram_cases:
            selected_grammatical_case = self._sample_grammatical_case(gram_cases)

        return selected_number_pattern, selected_grammatical_case

    def _sample_number_pattern(self, perf, db_service):
        """Sample to find the weakest number pattern."""
        number_patterns = perf.get("number_patterns", {})
        if not number_patterns:
            # No data, pick a random pattern
            random_row = random.choice(db_service.rows)
            return self._determine_number_pattern(random_row["number"])

        pattern_samples = {}
        for pattern, stats in number_patterns.items():
            alpha = stats["correct"] + 1
            beta_val = stats["incorrect"] + 1
            pattern_samples[pattern] = np.random.beta(alpha, beta_val)

        return min(pattern_samples, key=pattern_samples.get)

    def _sample_grammatical_case(self, gram_cases):
        """Sample to find the weakest grammatical case."""
        case_samples = {}
        for case, stats in gram_cases.items():
            alpha = stats["correct"] + 1
            beta_val = stats["incorrect"] + 1
            case_samples[case] = np.random.beta(alpha, beta_val)

        return min(case_samples, key=case_samples.get)

    def _find_matching_row(self, db_service, selected_number_pattern):
        """Find a row matching the selected number pattern."""
        matching_rows = []
        for row in db_service.rows:
            row_pattern = self._determine_number_pattern(row["number"])
            if row_pattern == selected_number_pattern:
                matching_rows.append(row)

        # If no matching rows, return None
        if not matching_rows:
            return None

        # Select a random row from matching rows
        return random.choice(matching_rows)

    def _determine_number_pattern(self, number):
        """Determine the pattern of a number.

        This helps categorize numbers for more targeted learning.
        """
        if number < 10:
            return "single_digit"
        elif number < 20:
            return "teens"
        elif number % 10 == 0:
            return "decade"
        else:
            return "compound"

    def get_weak_areas(self, session):
        """Identify weak areas for the user.

        Returns:
            Dictionary of weak areas by category
        """
        if "performance" not in session:
            return {}

        perf = session["performance"]
        weak_areas = {}

        # Analyze each category
        categories = {
            "exercise_types": "Exercise Types",
            "number_patterns": "Number Patterns",
            "grammatical_cases": "Grammatical Cases"
        }

        for cat_key, cat_name in categories.items():
            category = perf.get(cat_key, {})
            if not category:
                continue

            # Calculate success rate for each arm
            success_rates = {}
            for arm, stats in category.items():
                total = stats["correct"] + stats["incorrect"]
                if total > 1:  # Only consider arms with actual data
                    success_rates[arm] = stats["correct"] / total

            # Find the weakest areas (lowest success rates)
            if success_rates:
                sorted_arms = sorted(success_rates.items(), key=lambda x: x[1])
                weak_areas[cat_name] = [
                    {"name": arm, "success_rate": rate}
                    for arm, rate in sorted_arms[:3]  # Top 3 weakest
                ]

        return weak_areas
