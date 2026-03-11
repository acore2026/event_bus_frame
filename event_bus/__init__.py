"""
Event Bus Framework - A RESTful event subscription and publishing framework
"""

from .client import EventBusClient, EventHandler
from .models import Event, Subscription, EventType
from .exceptions import EventBusError, ConnectionError, PublishError

__version__ = "1.0.0"
__all__ = [
    "EventBusClient",
    "EventHandler",
    "Event",
    "Subscription",
    "EventType",
    "EventBusError",
    "ConnectionError",
    "PublishError",
]
