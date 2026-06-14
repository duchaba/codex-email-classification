class EmailResponseAgent:
    ALLOWED_CATEGORIES = {"Urgent Priority", "Work", "Personal"}

    def __init__(self, openai_service):
        self.openai_service = openai_service

    def draft(self, email):
        category = email.get("category")
        if category not in self.ALLOWED_CATEGORIES:
            raise ValueError("AI responses are available only for Urgent Priority, Work, and Personal emails.")
        if not self.openai_service or not self.openai_service.is_configured:
            raise RuntimeError("OpenAI is not configured. Add an API key in Setup first.")
        return self.openai_service.generate_email_response(email)
