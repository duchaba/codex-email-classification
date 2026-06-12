from collections import Counter

from .constants import CATEGORIES, CATEGORY_COLORS


class GroundTruthTestAgent:
    """Compare classifier output with expected labels in a synthetic fixture."""

    def evaluate(self, source_emails, predictions):
        if len(source_emails) != len(predictions):
            raise ValueError("Ground-truth records and predictions must have the same length.")
        if not source_emails:
            raise ValueError("Ground-truth test requires at least one email.")

        expected_by_id = {email.get("email_id"): email for email in source_emails}
        category_correct = 0
        subcategory_correct = 0
        exact_correct = 0
        expected_categories = Counter()
        predicted_categories = Counter()
        confusion = {expected: Counter() for expected in CATEGORIES}
        mismatches = []

        for prediction in predictions:
            email_id = prediction.get("email_id")
            expected = expected_by_id.get(email_id)
            if expected is None:
                raise ValueError(f"Prediction references unknown email_id {email_id}.")

            expected_category = str(expected.get("expected_category") or "")
            expected_subcategory = str(expected.get("expected_subcategory") or "")
            predicted_category = str(prediction.get("category") or "")
            predicted_subcategory = str(prediction.get("subcategory") or "")
            if not expected_category:
                raise ValueError(f"Ground truth is missing expected_category for {email_id}.")

            category_match = predicted_category == expected_category
            subcategory_match = predicted_subcategory == expected_subcategory
            category_correct += int(category_match)
            subcategory_correct += int(subcategory_match)
            exact_correct += int(category_match and subcategory_match)
            expected_categories[expected_category] += 1
            predicted_categories[predicted_category] += 1
            confusion.setdefault(expected_category, Counter())[predicted_category] += 1

            if not (category_match and subcategory_match) and len(mismatches) < 25:
                mismatches.append(
                    {
                        "email_id": email_id,
                        "subject": expected.get("subject", ""),
                        "expected_category": expected_category,
                        "predicted_category": predicted_category,
                        "expected_subcategory": expected_subcategory,
                        "predicted_subcategory": predicted_subcategory,
                    }
                )

        total = len(source_emails)
        labels = list(CATEGORIES)
        for label in sorted(set(expected_categories) | set(predicted_categories)):
            if label and label not in labels:
                labels.append(label)

        return {
            "total": total,
            "category_accuracy": round(category_correct / total, 4),
            "subcategory_accuracy": round(subcategory_correct / total, 4),
            "exact_accuracy": round(exact_correct / total, 4),
            "category_correct": category_correct,
            "subcategory_correct": subcategory_correct,
            "exact_correct": exact_correct,
            "chart": {
                "labels": labels,
                "expected": [expected_categories[label] for label in labels],
                "predicted": [predicted_categories[label] for label in labels],
                "colors": [CATEGORY_COLORS.get(label, "#a8aeb9") for label in labels],
            },
            "confusion_matrix": {
                "labels": labels,
                "rows": [
                    {
                        "expected": expected,
                        "predicted": [confusion.get(expected, Counter())[label] for label in labels],
                    }
                    for expected in labels
                ],
            },
            "mismatches": mismatches,
        }

