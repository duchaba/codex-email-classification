from .constants import CATEGORIES, LEGACY_CATEGORY_ALIASES, SUBCATEGORY_TO_PRIMARY


class CategoryRegroupAgent:
    def process(self, emails):
        regrouped = []
        for email in emails:
            original = LEGACY_CATEGORY_ALIASES.get(email.get("category"), email.get("category"))
            subcategory = email.get("subcategory") or ""

            if original in SUBCATEGORY_TO_PRIMARY:
                category = SUBCATEGORY_TO_PRIMARY[original]
                subcategory = original
            elif original in CATEGORIES:
                category = original
            else:
                category = "Personal"

            urgency = str(email.get("urgency_level") or "low").lower()
            if urgency == "high" and category in {"Work", "Personal"}:
                if not subcategory:
                    subcategory = category
                category = "Urgent Priority"

            email["category"] = category
            email["primary_category"] = category
            email["subcategory"] = subcategory
            email["secondary_categories"] = [
                label
                for label in (email.get("secondary_categories") or [])
                if label not in CATEGORIES and label != subcategory
            ]
            regrouped.append(email)
        return regrouped
