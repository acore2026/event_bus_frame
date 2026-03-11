"""
Event Bus Client SDK for services to subscribe and publish events
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
from functools import wraps

import httpx
from fastapi import FastAPI, Request, HTTPException
import uvicorn

from .models import (
    Event, EventType, Subscription, PublishRequest, SubscribeRequest,
    EventPriority
)
from .exceptions import ConnectionError, PublishError, SubscriptionError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("event_bus.client")


class EventHandler:
    """Decorator-based event handler registry"""

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {
            "broadcast": [],
            "direct": [],
            "topic": {},  # topic name -> handlers
        }
        self._topic_handlers: Dict[str, List[Callable]] = {}

    def on_broadcast(self, func: Callable) -> Callable:
        """Register handler for broadcast events"""
        self._handlers["broadcast"].append(func)
        return func

    def on_direct(self, func: Callable) -> Callable:
        """Register handler for direct events"""
        self._handlers["direct"].append(func)
        return func

    def on_topic(self, topic: str) -> Callable:
        """Register handler for specific topic"""
        def decorator(func: Callable) -> Callable:
            if topic not in self._topic_handlers:
                self._topic_handlers[topic] = []
            self._topic_handlers[topic].append(func)
            return func
        return decorator

    def on_event(self, event_type: EventType, topic: Optional[str] = None) -> Callable:
        """Generic event handler decorator"""
        def decorator(func: Callable) -> Callable:
            if event_type == EventType.TOPIC and topic:
                if topic not in self._topic_handlers:
                    self._topic_handlers[topic] = []
                self._topic_handlers[topic].append(func)
            else:
                self._handlers[event_type.value].append(func)
            return func
        return decorator

    async def handle(self, event: Event) -> List[Any]:
        """Execute all handlers for the given event"""
        results = []
        handlers_to_call = []

        # Get handlers based on event type
        if event.event_type == EventType.BROADCAST:
            handlers_to_call.extend(self._handlers["broadcast"])
        elif event.event_type == EventType.DIRECT:
            handlers_to_call.extend(self._handlers["direct"])

        # Add topic-specific handlers
        if event.topic and event.topic in self._topic_handlers:
            handlers_to_call.extend(self._topic_handlers[event.topic])

        # Execute handlers
        for handler in handlers_to_call:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(event)
                else:
                    result = handler(event)
                results.append(result)
            except Exception as e:
                logger.error(f"Handler error for event {event.id}: {e}")
                results.append(e)

        return results


class EventBusClient:
    """
    Event Bus Client for publishing and subscribing to events

    Usage:
        client = EventBusClient(
            service_name="order-service",
            service_url="http://localhost:8001",
            event_bus_url="http://localhost:8000"
        )

        @client.handler.on_topic("order.created")
        async def handle_order_created(event: Event):
            print(f"Order created: {event.payload}")

        await client.start()
    """

    def __init__(
        self,
        service_name: str,
        service_url: str,
        event_bus_url: str = "http://localhost:8000",
        event_types: Optional[List[EventType]] = None,
        topics: Optional[List[str]] = None,
        heartbeat_interval: int = 30,
        auto_reconnect: bool = True
    ):
        self.service_name = service_name
        self.service_url = service_url
        self.event_bus_url = event_bus_url.rstrip("/")
        self.event_types = event_types or [EventType.BROADCAST]
        self.topics = topics or []
        self.heartbeat_interval = heartbeat_interval
        self.auto_reconnect = auto_reconnect

        self.handler = EventHandler()
        self._subscription_id: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._app: Optional[FastAPI] = None
        self._server: Optional[uvicorn.Server] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def subscribe(self) -> str:
        """Subscribe this service to the event bus"""
        client = await self._get_client()

        request = SubscribeRequest(
            service_name=self.service_name,
            service_url=f"{self.service_url}/webhook",
            event_types=self.event_types,
            topics=self.topics
        )

        try:
            response = await client.post(
                f"{self.event_bus_url}/api/v1/subscribe",
                json=request.model_dump()
            )
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                self._subscription_id = data["subscription_id"]
                logger.info(f"Subscribed successfully: {self._subscription_id}")
                return self._subscription_id
            else:
                raise SubscriptionError(f"Subscription failed: {data.get('message')}")

        except httpx.HTTPError as e:
            raise ConnectionError(f"Failed to connect to event bus: {e}")

    async def unsubscribe(self) -> bool:
        """Unsubscribe this service from the event bus"""
        if not self._subscription_id:
            return True

        client = await self._get_client()

        try:
            response = await client.post(
                f"{self.event_bus_url}/api/v1/unsubscribe",
                json={
                    "service_name": self.service_name,
                    "subscription_id": self._subscription_id
                }
            )
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                logger.info(f"Unsubscribed: {self._subscription_id}")
                self._subscription_id = None
                return True
            return False

        except httpx.HTTPError as e:
            logger.error(f"Unsubscribe error: {e}")
            return False

    async def publish(
        self,
        payload: Dict[str, Any],
        event_type: EventType = EventType.BROADCAST,
        topic: Optional[str] = None,
        target: Optional[str] = None,
        priority: EventPriority = EventPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Publish an event to the event bus

        Args:
            payload: Event data
            event_type: Type of event
            topic: Topic name (for TOPIC events)
            target: Target service (for DIRECT events)
            priority: Event priority
            metadata: Additional metadata

        Returns:
            event_id: The ID of the published event
        """
        client = await self._get_client()

        request = PublishRequest(
            event_type=event_type,
            topic=topic,
            target=target,
            payload=payload,
            priority=priority,
            metadata=metadata or {}
        )

        try:
            response = await client.post(
                f"{self.event_bus_url}/api/v1/publish",
                json=request.model_dump()
            )
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                logger.debug(f"Published event: {data['event_id']}")
                return data["event_id"]
            else:
                raise PublishError(f"Publish failed: {data.get('message')}")

        except httpx.HTTPError as e:
            raise PublishError(f"Failed to publish event: {e}")

    async def publish_topic(
        self,
        topic: str,
        payload: Dict[str, Any],
        **kwargs
    ) -> str:
        """Convenience method for publishing to a topic"""
        return await self.publish(
            payload=payload,
            event_type=EventType.TOPIC,
            topic=topic,
            **kwargs
        )

    async def send_direct(
        self,
        target: str,
        payload: Dict[str, Any],
        **kwargs
    ) -> str:
        """Convenience method for direct messaging"""
        return await self.publish(
            payload=payload,
            event_type=EventType.DIRECT,
            target=target,
            **kwargs
        )

    async def _send_heartbeat(self):
        """Send periodic heartbeat to event bus"""
        while self._is_running:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                if not self._subscription_id:
                    continue

                client = await self._get_client()
                response = await client.post(
                    f"{self.event_bus_url}/api/v1/heartbeat",
                    json={
                        "service_name": self.service_name,
                        "subscription_id": self._subscription_id
                    }
                )

                if response.status_code != 200:
                    logger.warning(f"Heartbeat failed: {response.status_code}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    def _create_app(self) -> FastAPI:
        """Create FastAPI app for receiving events"""
        app = FastAPI(title=f"{self.service_name} - Event Receiver")

        @app.post("/webhook")
        async def webhook(request: Request):
            """Receive events from event bus"""
            try:
                data = await request.json()
                event = Event(**data)

                logger.debug(f"Received event: {event.id} - {event.event_type}")

                # Process event through handlers
                results = await self.handler.handle(event)

                return {
                    "success": True,
                    "event_id": event.id,
                    "processed": len(results)
                }

            except Exception as e:
                logger.error(f"Webhook error: {e}")
                raise HTTPException(status_code=400, detail=str(e))

        @app.get("/health")
        async def health():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "service": self.service_name,
                "subscription_id": self._subscription_id
            }

        return app

    async def start(self, host: str = "0.0.0.0", port: int = 8001):
        """
        Start the client service

        This will:
        1. Subscribe to the event bus
        2. Start the webhook server
        3. Begin sending heartbeats
        """
        self._is_running = True

        # Subscribe to event bus
        await self.subscribe()

        # Create and start webhook server
        self._app = self._create_app()

        config = uvicorn.Config(
            app=self._app,
            host=host,
            port=port,
            log_level="info"
        )
        self._server = uvicorn.Server(config)

        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._send_heartbeat())

        logger.info(f"Starting {self.service_name} on {host}:{port}")

        # Run server
        await self._server.serve()

    async def stop(self):
        """Stop the client service"""
        self._is_running = False

        # Cancel heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Unsubscribe
        await self.unsubscribe()

        # Close server
        if self._server:
            self._server.should_exit = True

        # Close HTTP client
        if self._client:
            await self._client.aclose()

        logger.info(f"{self.service_name} stopped")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
