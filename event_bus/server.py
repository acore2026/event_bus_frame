"""
Event Bus Server - Central hub for event distribution
"""

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from .models import (
    Event, EventType, Subscription, PublishRequest, SubscribeRequest,
    SubscribeResponse, PublishResponse, UnsubscribeRequest, HealthStatus,
    EventDeliveryStatus, EventPriority
)
from .exceptions import ValidationError, DeliveryError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("event_bus.server")


class SubscriptionManager:
    """Manages all subscriptions to the event bus"""

    def __init__(self):
        self._subscriptions: Dict[str, Subscription] = {}
        self._service_subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._topic_subscribers: Dict[str, Set[str]] = defaultdict(set)
        self._event_type_subscribers: Dict[str, Set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def add_subscription(self, subscription: Subscription) -> str:
        """Add a new subscription"""
        async with self._lock:
            sub_id = subscription.id
            self._subscriptions[sub_id] = subscription
            self._service_subscriptions[subscription.service_name].add(sub_id)

            # Index by event types
            for et in subscription.event_types:
                self._event_type_subscribers[et.value].add(sub_id)

            # Index by topics
            for topic in subscription.topics:
                self._topic_subscribers[topic].add(sub_id)

            logger.info(f"New subscription: {subscription.service_name} ({sub_id})")
            return sub_id

    async def remove_subscription(self, sub_id: str) -> bool:
        """Remove a subscription"""
        async with self._lock:
            if sub_id not in self._subscriptions:
                return False

            sub = self._subscriptions[sub_id]

            # Remove from service index
            self._service_subscriptions[sub.service_name].discard(sub_id)
            if not self._service_subscriptions[sub.service_name]:
                del self._service_subscriptions[sub.service_name]

            # Remove from event type index
            for et in sub.event_types:
                self._event_type_subscribers[et.value].discard(sub_id)

            # Remove from topic index
            for topic in sub.topics:
                self._topic_subscribers[topic].discard(sub_id)

            del self._subscriptions[sub_id]

            logger.info(f"Removed subscription: {sub_id}")
            return True

    async def update_heartbeat(self, sub_id: str) -> bool:
        """Update last heartbeat timestamp"""
        async with self._lock:
            if sub_id in self._subscriptions:
                self._subscriptions[sub_id].last_heartbeat = datetime.utcnow()
                return True
            return False

    async def get_subscriptions_for_event(self, event: Event) -> List[Subscription]:
        """Get all subscriptions that should receive this event"""
        async with self._lock:
            target_sub_ids: Set[str] = set()

            if event.event_type == EventType.BROADCAST:
                # All subscribers that listen to broadcasts
                target_sub_ids.update(
                    self._event_type_subscribers.get(EventType.BROADCAST.value, set())
                )

            elif event.event_type == EventType.DIRECT:
                # Only target service
                if event.target:
                    for sub_id in self._service_subscriptions.get(event.target, set()):
                        target_sub_ids.add(sub_id)

            elif event.event_type == EventType.TOPIC:
                # Subscribers to this topic
                if event.topic:
                    target_sub_ids.update(
                        self._topic_subscribers.get(event.topic, set())
                    )

            return [self._subscriptions[sid] for sid in target_sub_ids
                    if sid in self._subscriptions and self._subscriptions[sid].is_active]

    async def get_all_subscriptions(self) -> List[Subscription]:
        """Get all active subscriptions"""
        async with self._lock:
            return list(self._subscriptions.values())

    async def cleanup_stale_subscriptions(self, max_age_seconds: int = 120):
        """Remove subscriptions that haven't sent heartbeat"""
        async with self._lock:
            now = datetime.utcnow()
            stale_ids = []

            for sub_id, sub in self._subscriptions.items():
                if sub.last_heartbeat:
                    age = (now - sub.last_heartbeat).total_seconds()
                    if age > max_age_seconds:
                        stale_ids.append(sub_id)

            for sub_id in stale_ids:
                await self.remove_subscription(sub_id)
                logger.warning(f"Removed stale subscription: {sub_id}")


class EventDeliveryManager:
    """Manages event delivery to subscribers"""

    def __init__(self, subscription_manager: SubscriptionManager):
        self._subscription_manager = subscription_manager
        self._delivery_status: Dict[str, EventDeliveryStatus] = {}
        self._stats = {
            "total_events": 0,
            "delivered": 0,
            "failed": 0
        }
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def deliver_event(
        self,
        event: Event,
        subscription: Subscription
    ) -> EventDeliveryStatus:
        """Deliver an event to a subscriber"""
        delivery_id = f"{event.id}:{subscription.id}"

        status = EventDeliveryStatus(
            event_id=event.id,
            subscription_id=subscription.id,
            status="pending",
            attempts=0
        )
        self._delivery_status[delivery_id] = status

        client = await self._get_client()
        retry_policy = subscription.retry_policy

        max_retries = retry_policy.get("max_retries", 3)
        retry_interval = retry_policy.get("retry_interval", 5)
        timeout = retry_policy.get("timeout", 30)

        for attempt in range(max_retries):
            try:
                status.attempts += 1
                status.status = "retrying" if attempt > 0 else "pending"
                status.last_attempt = datetime.utcnow()

                response = await client.post(
                    subscription.service_url,
                    json=event.model_dump(),
                    timeout=timeout
                )
                response.raise_for_status()

                status.status = "delivered"
                self._stats["delivered"] += 1
                logger.debug(f"Delivered {event.id} to {subscription.service_name}")
                return status

            except Exception as e:
                status.error_message = str(e)
                logger.warning(
                    f"Delivery attempt {attempt + 1} failed for {event.id} "
                    f"to {subscription.service_name}: {e}"
                )

                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_interval)

        status.status = "failed"
        self._stats["failed"] += 1
        logger.error(
            f"Failed to deliver {event.id} to {subscription.service_name} "
            f"after {max_retries} attempts"
        )
        return status

    async def close(self):
        if self._client:
            await self._client.aclose()


class EventBusServer:
    """
    Event Bus Server - Central hub for event distribution
    """

    def __init__(
        self,
        cleanup_interval: int = 60,
        max_subscription_age: int = 120
    ):
        self.subscription_manager = SubscriptionManager()
        self.delivery_manager = EventDeliveryManager(self.subscription_manager)
        self._cleanup_interval = cleanup_interval
        self._max_subscription_age = max_subscription_age
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_time = time.time()
        self._app: Optional[FastAPI] = None

    async def _cleanup_loop(self):
        """Periodic cleanup of stale subscriptions"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self.subscription_manager.cleanup_stale_subscriptions(
                    self._max_subscription_age
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    def create_app(self) -> FastAPI:
        """Create FastAPI application"""

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Event Bus Server started")
            yield
            # Shutdown
            if self._cleanup_task:
                self._cleanup_task.cancel()
            await self.delivery_manager.close()
            logger.info("Event Bus Server stopped")

        app = FastAPI(
            title="Event Bus Server",
            description="RESTful Event Subscription and Publishing Framework",
            version="1.0.0",
            lifespan=lifespan
        )

        @app.post("/api/v1/subscribe", response_model=SubscribeResponse)
        async def subscribe(request: SubscribeRequest):
            """Subscribe a service to receive events"""
            try:
                subscription = Subscription(
                    service_name=request.service_name,
                    service_url=request.service_url,
                    event_types=request.event_types,
                    topics=request.topics,
                    retry_policy=request.retry_policy or {
                        "max_retries": 3,
                        "retry_interval": 5,
                        "timeout": 30
                    }
                )

                sub_id = await self.subscription_manager.add_subscription(subscription)

                return SubscribeResponse(
                    success=True,
                    subscription_id=sub_id,
                    message="Subscription created successfully"
                )

            except Exception as e:
                logger.error(f"Subscribe error: {e}")
                raise HTTPException(status_code=400, detail=str(e))

        @app.post("/api/v1/unsubscribe")
        async def unsubscribe(request: UnsubscribeRequest):
            """Unsubscribe a service"""
            if request.subscription_id:
                success = await self.subscription_manager.remove_subscription(
                    request.subscription_id
                )
            else:
                # Remove all subscriptions for this service
                subs = await self.subscription_manager.get_all_subscriptions()
                success = False
                for sub in subs:
                    if sub.service_name == request.service_name:
                        await self.subscription_manager.remove_subscription(sub.id)
                        success = True

            return {"success": success, "message": "Unsubscribed" if success else "Not found"}

        @app.post("/api/v1/publish", response_model=PublishResponse)
        async def publish(request: PublishRequest, background_tasks: BackgroundTasks):
            """Publish an event to the bus"""
            try:
                event = Event(
                    event_type=request.event_type,
                    topic=request.topic,
                    source="event-bus",  # Will be overridden by client
                    target=request.target,
                    payload=request.payload,
                    priority=request.priority,
                    metadata=request.metadata or {}
                )

                # Get target subscriptions
                subscriptions = await self.subscription_manager.get_subscriptions_for_event(event)

                if not subscriptions:
                    return PublishResponse(
                        success=True,
                        event_id=event.id,
                        message="Event published but no subscribers",
                        delivered_count=0,
                        failed_count=0
                    )

                # Deliver in background
                delivered = 0
                failed = 0

                for sub in subscriptions:
                    result = await self.delivery_manager.deliver_event(event, sub)
                    if result.status == "delivered":
                        delivered += 1
                    else:
                        failed += 1

                return PublishResponse(
                    success=True,
                    event_id=event.id,
                    message=f"Event delivered to {delivered} subscribers",
                    delivered_count=delivered,
                    failed_count=failed
                )

            except Exception as e:
                logger.error(f"Publish error: {e}")
                raise HTTPException(status_code=400, detail=str(e))

        @app.post("/api/v1/heartbeat")
        async def heartbeat(request: Request):
            """Receive heartbeat from subscribers"""
            data = await request.json()
            sub_id = data.get("subscription_id")

            if not sub_id:
                raise HTTPException(status_code=400, detail="subscription_id required")

            success = await self.subscription_manager.update_heartbeat(sub_id)

            if not success:
                raise HTTPException(status_code=404, detail="Subscription not found")

            return {"success": True, "message": "Heartbeat received"}

        @app.get("/api/v1/subscriptions")
        async def list_subscriptions():
            """List all active subscriptions"""
            subs = await self.subscription_manager.get_all_subscriptions()
            return {
                "subscriptions": [sub.model_dump() for sub in subs],
                "count": len(subs)
            }

        @app.get("/api/v1/stats")
        async def get_stats():
            """Get event bus statistics"""
            return {
                "subscriptions": len(await self.subscription_manager.get_all_subscriptions()),
                **self.delivery_manager._stats
            }

        @app.get("/health", response_model=HealthStatus)
        async def health():
            """Health check endpoint"""
            return HealthStatus(
                status="healthy",
                timestamp=datetime.utcnow(),
                uptime_seconds=time.time() - self._start_time,
                total_subscriptions=len(await self.subscription_manager.get_all_subscriptions()),
                total_events_processed=self.delivery_manager._stats["total_events"]
            )

        self._app = app
        return app


# Create default server instance
def create_server() -> FastAPI:
    """Factory function to create Event Bus Server"""
    server = EventBusServer()
    return server.create_app()
