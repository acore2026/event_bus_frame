"""
Data models for Event Bus Framework
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional, Dict, List
from pydantic import BaseModel, Field
import uuid


class EventType(str, Enum):
    """Event types supported by the event bus"""
    BROADCAST = "broadcast"  # Broadcast to all subscribers
    DIRECT = "direct"        # Direct to specific service
    TOPIC = "topic"          # Pub/Sub topic-based


class EventPriority(int, Enum):
    """Event priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class Event(BaseModel):
    """Event model representing a message in the event bus"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.BROADCAST
    topic: Optional[str] = None
    source: str = Field(..., description="Service that published the event")
    target: Optional[str] = Field(None, description="Target service for direct events")
    payload: Dict[str, Any] = Field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Subscription(BaseModel):
    """Subscription model for event consumers"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = Field(..., description="Name of the subscribing service")
    service_url: str = Field(..., description="Callback URL for the service")
    event_types: List[EventType] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    subscribed_at: datetime = Field(default_factory=datetime.utcnow)
    last_heartbeat: Optional[datetime] = None
    is_active: bool = True
    retry_policy: Dict[str, Any] = Field(default_factory=lambda: {
        "max_retries": 3,
        "retry_interval": 5,
        "timeout": 30
    })

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PublishRequest(BaseModel):
    """Request model for publishing events"""
    event_type: EventType = EventType.BROADCAST
    topic: Optional[str] = None
    target: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    metadata: Optional[Dict[str, Any]] = None


class PublishResponse(BaseModel):
    """Response model for publish requests"""
    success: bool
    event_id: str
    message: str
    delivered_count: int = 0
    failed_count: int = 0


class SubscribeRequest(BaseModel):
    """Request model for subscription"""
    service_name: str
    service_url: str
    event_types: List[EventType] = Field(default_factory=lambda: [EventType.BROADCAST])
    topics: List[str] = Field(default_factory=list)
    retry_policy: Optional[Dict[str, Any]] = None


class SubscribeResponse(BaseModel):
    """Response model for subscription requests"""
    success: bool
    subscription_id: str
    message: str


class UnsubscribeRequest(BaseModel):
    """Request model for unsubscription"""
    service_name: str
    subscription_id: Optional[str] = None


class HealthStatus(BaseModel):
    """Health check status model"""
    status: str
    timestamp: datetime
    uptime_seconds: float
    total_subscriptions: int
    total_events_processed: int
    version: str = "1.0.0"


class EventDeliveryStatus(BaseModel):
    """Event delivery status tracking"""
    event_id: str
    subscription_id: str
    status: str  # pending, delivered, failed, retrying
    attempts: int = 0
    last_attempt: Optional[datetime] = None
    error_message: Optional[str] = None
