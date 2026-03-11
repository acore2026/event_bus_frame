"""
Example Order Service - Demonstrates Event Bus Client usage

This service:
1. Publishes order.created events
2. Subscribes to payment.completed events
3. Handles inventory.reserved events
"""

import asyncio
import logging
from event_bus import EventBusClient, EventHandler, Event, EventType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("order_service")


class OrderService:
    """Example order service that uses event bus"""

    def __init__(self):
        self.client = EventBusClient(
            service_name="order-service",
            service_url="http://localhost:8001",
            event_bus_url="http://localhost:8000",
            event_types=[EventType.BROADCAST, EventType.DIRECT, EventType.TOPIC],
            topics=["payment.completed", "inventory.reserved", "shipping.ready"]
        )
        self.orders = {}

    def setup_handlers(self):
        """Setup event handlers"""

        @self.client.handler.on_topic("payment.completed")
        async def handle_payment_completed(event: Event):
            """Handle payment completion"""
            order_id = event.payload.get("order_id")
            payment_status = event.payload.get("status")

            logger.info(f"Payment completed for order {order_id}: {payment_status}")

            if order_id in self.orders:
                self.orders[order_id]["payment_status"] = payment_status

                # Trigger inventory reservation
                await self.client.publish_topic(
                    topic="inventory.reserve",
                    payload={
                        "order_id": order_id,
                        "items": self.orders[order_id].get("items", [])
                    }
                )

        @self.client.handler.on_topic("inventory.reserved")
        async def handle_inventory_reserved(event: Event):
            """Handle inventory reservation"""
            order_id = event.payload.get("order_id")
            reserved = event.payload.get("reserved", False)

            logger.info(f"Inventory reserved for order {order_id}: {reserved}")

            if order_id in self.orders:
                self.orders[order_id]["inventory_status"] = "reserved" if reserved else "failed"

                if reserved:
                    # Trigger shipping
                    await self.client.publish_topic(
                        topic="shipping.request",
                        payload={
                            "order_id": order_id,
                            "address": self.orders[order_id].get("shipping_address")
                        }
                    )

        @self.client.handler.on_direct
        async def handle_direct_message(event: Event):
            """Handle direct messages to this service"""
            logger.info(f"Received direct message: {event.payload}")

    async def create_order(self, user_id: str, items: list, shipping_address: dict):
        """Create a new order and publish event"""
        order_id = f"ORD-{len(self.orders) + 1:06d}"

        order = {
            "id": order_id,
            "user_id": user_id,
            "items": items,
            "shipping_address": shipping_address,
            "status": "created",
            "payment_status": "pending",
            "inventory_status": "pending"
        }

        self.orders[order_id] = order

        # Publish order created event
        await self.client.publish_topic(
            topic="order.created",
            payload=order,
            priority=2  # NORMAL
        )

        logger.info(f"Order created: {order_id}")
        return order_id

    async def run(self):
        """Run the service"""
        self.setup_handlers()
        await self.client.start(host="0.0.0.0", port=8001)


async def demo():
    """Demo function showing how the service works"""
    service = OrderService()

    # Start service in background
    task = asyncio.create_task(service.run())

    # Wait for service to start and subscribe
    await asyncio.sleep(2)

    try:
        # Simulate creating orders
        for i in range(3):
            await service.create_order(
                user_id=f"user_{i}",
                items=[
                    {"product_id": f"PROD-{j}", "quantity": j + 1}
                    for j in range(2)
                ],
                shipping_address={
                    "street": f"{i} Main St",
                    "city": "Beijing",
                    "zip": "100000"
                }
            )
            await asyncio.sleep(1)

        # Keep running
        await asyncio.sleep(60)

    except KeyboardInterrupt:
        pass
    finally:
        await service.client.stop()


if __name__ == "__main__":
    print("Order Service Example")
    print("=" * 50)
    print("This service will:")
    print("1. Connect to event bus at http://localhost:8000")
    print("2. Listen on http://localhost:8001")
    print("3. Subscribe to payment.completed, inventory.reserved topics")
    print("4. Publish order.created events")
    print("=" * 50)

    try:
        asyncio.run(demo())
    except KeyboardInterrupt:
        print("\nService stopped")
