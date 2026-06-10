from collections import Counter

from .constants import CATEGORIES, CATEGORY_COLORS


class ChartAgent:
    def build(self, emails):
        counts = Counter(email.get("category") for email in emails)
        labels = [category for category in CATEGORIES if counts.get(category)]
        return {
            "labels": labels,
            "values": [counts[label] for label in labels],
            "colors": [CATEGORY_COLORS[label] for label in labels],
            "radar_max": max([counts[label] for label in labels] or [1]),
        }
