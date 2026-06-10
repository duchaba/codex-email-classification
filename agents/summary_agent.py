from collections import Counter


class SummaryAgent:
    def build(self, emails):
        counts = Counter(email.get("category", "Other / Needs Review") for email in emails)
        top = counts.most_common(3)
        urgent = [email for email in emails if email.get("category") == "Urgent Priority"]
        low_confidence = [email for email in emails if float(email.get("confidence_score") or 0) < 0.6]
        category_summaries = {
            category: f"{count} message{'s' if count != 1 else ''} ready for review."
            for category, count in counts.items()
        }
        return {
            "total": len(emails),
            "top_categories": [{"category": category, "count": count} for category, count in top],
            "urgent_count": len(urgent),
            "low_confidence_count": len(low_confidence),
            "category_summaries": category_summaries,
        }
