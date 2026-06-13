import re

from .base_email_classifier_agent import BaseEmailClassifierAgent
from .constants import CATEGORIES, LEGACY_CATEGORY_ALIASES, PRIMARY_CATEGORY_PRIORITY, SUBCATEGORY_TO_PRIMARY


class MockEmailClassifierAgent(BaseEmailClassifierAgent):
    def classify(self, emails, _prompt):
        predictions = [self._classify_email(email) for email in emails]
        return self._finalize(emails, predictions)

    def _classify_email(self, email):
        text = " ".join(
            [
                email.get("sender_email", ""),
                email.get("sender_name", ""),
                email.get("subject", ""),
                email.get("body_preview", ""),
            ]
        ).lower()
        rules = [
            ("Spam", "", ["claim your", "cash reward", "bank details", "crypto giveaway", "wire funds", "urgent winner"]),
            ("Work", "", ["elvtr.com", "genai-incubator.com", "approval", "action items", "deadline", "launch review", "client", "project update"]),
            ("Personal", "Bills & Utilities", ["bill is due", "payment due", "utility", "electric bill", "invoice due"]),
            ("Personal", "Banking", ["bank", "card purchase", "account alert", "transaction", "deposit"]),
            ("Personal", "Personal Projects", ["kickstarter", "author", "book", "alumni", "personal project", "creator"]),
            ("Personal", "Friends", ["dinner", "weekend", "old group", "catch up", "coffee?"]),
            ("Social Media", "Invitations & Events", ["invitation", "you are invited", "meetup", "rsvp", "event"]),
            ("Social Media", "News & Releases", ["newsletter", "roundup", "release", "news", "digest", "brief"]),
            ("Social Media", "Sales & Marketing", ["save ", "discount", "sale", "upgrade", "offer", "buy now", "marketing"]),
            ("Social Media", "", ["linkedin", "instagram", "facebook", "social", "searches", "new follower"]),
            ("Personal", "", ["family", "appointment", "personal", "reminder"]),
        ]
        matches = []
        for category, subcategory, keywords in rules:
            score = sum(1 for keyword in keywords if keyword in text)
            if score:
                matches.append((score, category, subcategory))
        matches.sort(key=lambda item: (-item[0], PRIMARY_CATEGORY_PRIORITY.index(item[1])))

        if matches:
            top_score, base_category, subcategory = matches[0]
        else:
            supplied = LEGACY_CATEGORY_ALIASES.get(email.get("category"), email.get("category"))
            if supplied in SUBCATEGORY_TO_PRIMARY:
                base_category = SUBCATEGORY_TO_PRIMARY[supplied]
                subcategory = supplied
            elif supplied in CATEGORIES:
                base_category = supplied
                subcategory = email.get("subcategory") or ""
            else:
                base_category = "Personal"
                subcategory = ""
            top_score = 0

        urgency = "high" if any(word in text for word in ["today", "urgent", "due", "deadline", "approval", "immediately", "asap"]) else "medium" if base_category in {"Work", "Personal"} else "low"
        category = "Urgent Priority" if urgency == "high" and base_category in {"Work", "Personal"} else base_category
        if category == "Urgent Priority" and not subcategory:
            subcategory = base_category

        secondary = []
        for _score, matched_category, matched_subcategory in matches[1:3]:
            label = matched_subcategory or matched_category
            if label not in CATEGORIES and label not in secondary and label != subcategory:
                secondary.append(label)

        confidence = min(0.98, 0.68 + top_score * 0.09) if matches else 0.46
        subject = email.get("subject") or "This message"
        preview = email.get("body_preview") or "Open the email to review its contents."
        sentence = re.split(r"(?<=[.!?])\s+", preview.strip())[0].strip()
        if sentence and sentence[-1] not in ".!?":
            sentence += "."
        detail = subcategory or base_category
        reason = f"Matched {detail.lower()} signals in the sender, subject, or message text." if matches else "The message lacks enough distinctive context for a high-confidence classification."
        return {
            **email,
            "category": category,
            "primary_category": category,
            "subcategory": subcategory,
            "secondary_categories": secondary,
            "one_sentence_summary": sentence or f"Review {subject}.",
            "summary": sentence or f"Review {subject}.",
            "confidence_score": round(confidence, 2),
            "classification_reason": reason,
            "reason": reason,
            "urgency_level": urgency,
        }
