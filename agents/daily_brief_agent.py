from collections import Counter
import re


class DailyBriefAgent:
    def __init__(self, openai_service=None):
        self.openai_service = openai_service

    def build(self, emails, use_ai=False):
        fallback = self._fallback(emails)
        if not use_ai or not self.openai_service or not self.openai_service.is_configured:
            return {"text": fallback, "generated_by": "local"}
        try:
            text = self._format_for_quick_read(self.openai_service.generate_daily_brief(emails))
            return {"text": text, "generated_by": "ai"}
        except Exception:
            return {"text": fallback, "generated_by": "local-fallback"}

    @staticmethod
    def _format_for_quick_read(text):
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", str(text or "")) if part.strip()]
        if len(paragraphs) > 1:
            return "\n\n".join(paragraphs[:3])

        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", paragraphs[0] if paragraphs else "") if part.strip()]
        if len(sentences) < 2:
            return paragraphs[0] if paragraphs else ""
        if len(sentences) == 2:
            return "\n\n".join(sentences)

        midpoint = (len(sentences) + 1) // 2
        return " ".join(sentences[:midpoint]) + "\n\n" + " ".join(sentences[midpoint:])

    @staticmethod
    def _fallback(emails):
        if not emails:
            return "No classified mail yet. Your inbox is enjoying the quiet before the click."
        counts = Counter(email.get("category", "Personal") for email in emails)
        top_category, top_count = counts.most_common(1)[0]
        urgent_count = counts.get("Urgent Priority", 0)
        opening = f"Today’s inbox has {len(emails)} messages, led by {top_category} with {top_count}."
        if urgent_count:
            closing = f"There {'is' if urgent_count == 1 else 'are'} {urgent_count} priority message{'s' if urgent_count != 1 else ''} asking to skip the scenic route."
        else:
            closing = "Nothing is waving a red flag, so you can work through the stack without dramatic music."
        return f"{opening}\n\n{closing}"
