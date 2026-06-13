from .constants import CATEGORIES


class BaseEmailClassifierAgent:
    @staticmethod
    def _validate_one_prediction_per_email(source_emails, predictions):
        source_ids = [email.get("email_id") for email in source_emails]
        prediction_ids = [prediction.get("email_id") for prediction in predictions]
        if len(prediction_ids) != len(set(prediction_ids)):
            raise ValueError("Classifier returned duplicate email_id values.")
        if set(prediction_ids) != set(source_ids) or len(predictions) != len(source_emails):
            raise ValueError("Classifier must return exactly one result for every input email_id.")
        for prediction in predictions:
            category = prediction.get("category")
            if not isinstance(category, str) or category not in CATEGORIES:
                raise ValueError("Classifier must return one valid primary category as a string.")
            subcategory = prediction.get("subcategory", "")
            if not isinstance(subcategory, str):
                raise ValueError("Classifier subcategory must be a single string.")
            secondary = prediction.get("secondary_categories", [])
            if not isinstance(secondary, list):
                raise ValueError("Classifier secondary_categories must be a list.")
        by_id = {prediction["email_id"]: prediction for prediction in predictions}
        return [by_id[email_id] for email_id in source_ids]

    @staticmethod
    def _preserve_ground_truth(source_emails, predictions):
        """Ground-truth labels are immutable evaluation data, never classifier output."""
        source_by_id = {email.get("email_id"): email for email in source_emails}
        protected = (
            "expected_category",
            "expected_subcategory",
            "body_preview",
            "full_body_optional",
        )
        preserved = []
        for prediction in predictions:
            source = source_by_id.get(prediction.get("email_id"), {})
            result = dict(prediction)
            for field in protected:
                if field in source:
                    result[field] = source[field]
                else:
                    result.pop(field, None)
            preserved.append(result)
        return preserved

    def _finalize(self, source_emails, predictions):
        validated = self._validate_one_prediction_per_email(source_emails, predictions)
        return self._preserve_ground_truth(source_emails, validated)
