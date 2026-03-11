"""
Exception classes for Event Bus Framework
"""


class EventBusError(Exception):
    """Base exception for event bus errors"""
    pass


class ConnectionError(EventBusError):
    """Raised when connection to event bus fails"""
    pass


class PublishError(EventBusError):
    """Raised when publishing an event fails"""
    pass


class SubscriptionError(EventBusError):
    """Raised when subscription operation fails"""
    pass


class DeliveryError(EventBusError):
    """Raised when event delivery fails"""
    pass


class ValidationError(EventBusError):
    """Raised when event or subscription validation fails"""
    pass


class TimeoutError(EventBusError):
    """Raised when operation times out"""
    pass
