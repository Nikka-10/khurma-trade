class SubscriptionException(Exception):
    default_message = 'Something went wrong with your subscription.'

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)

class StaleStripeReferenceError(SubscriptionException):
    default_message = 'Your subscription record is out of date. Please subscribe again.'

class CardDeclinedError(SubscriptionException):
    default_message = 'Your card was declined.'

class PaymentServiceError(SubscriptionException):
    default_message = 'Payment service is temporarily unavailable. Please try again.'

class InvalidWebhookError(SubscriptionException):
    default_message = 'error with webhook.'