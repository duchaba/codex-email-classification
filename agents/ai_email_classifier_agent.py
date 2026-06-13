from .base_email_classifier_agent import BaseEmailClassifierAgent


class AIEmailClassifierAgent(BaseEmailClassifierAgent):
    def __init__(self, openai_service):
        self.openai_service = openai_service

    def classify(self, emails, prompt):
        if not self.openai_service or not self.openai_service.is_configured:
            raise RuntimeError("OpenAI classification is not configured.")
        predictions = self.openai_service.classify(emails, prompt)
        return self._finalize(emails, predictions)
