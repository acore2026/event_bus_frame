"""
Example Inventory Service - Manages inventory reservations

This service:
1. Subscribes to inventory.reserve events
2. Reserves inventory
3. Publishes inventory.reserved events
"""

import asyncio
import logging
import random
from event_bus import EventBusClient, Event, EventType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inventory_service")


class InventoryService:
    """Example inventory management service"""

    def __init__(self):
        self.client = EventBusClient(
            service_name="inventory-service",
            service_url="http://localhost:8003",
            event_bus_url="http://localhost:8000",
            event_types=[EventType.TOPIC],
            topics=["inventory.reserve", "inventory.release"]
        )
        self.inventory = {}
        self.reservations = {}

        # Initialize mock inventory
        for i in range(100):
            self.inventory[f"PROD-{i}"] = random.randint(10, 100)

    def setup_handlers(self):
        """Setup event handlers"""

        @self.client.handler.on_topic("inventory.reserve")
        async def handle_reserve(event: Event):
            """Reserve inventory for an order"""
            order_id = event.payload.get("order_id")
            items = event.payload.get("items", [])

            logger.info(f"Reserving inventory for order: {order_id}")

            # Check availability
            can_reserve = True
            for item in items:
                product_id = item.get("product_id")
                quantity = item.get("quantity", 1)

                if self.inventory.get(product_id, 0) < quantity:
                    can_reserve = False
                    break

            if can_reserve:
                # Reserve items
                for item in items:
                    product_id = item.get("product_id")
                    quantity = item.get("quantity", 1)
                    self.inventory[product_id] -= quantity

                self.reservations[order_id] = items
                logger.info(f"Inventory reserved for order {order_id}")
            else:
                logger.warning(f"Cannot reserve inventory for order {order_id}")

            # Publish result
            await self.client.publish_topic(
                topic="inventory.reserved",
                payload={
                    "order_id": order_id,
                    "reserved": can_reserve,
                    "items": items
                }
            )

        @self.client.handler.on_topic("inventory.release")
        async def handle_release(event: Event):
            """Release reserved inventory"""
            order_id = event.payload.get("order_id")

            if order_id in self.reservations:
                items = self.reservations[order_id]

                # Return items to inventory
                for item in items:
                    product_id = item.get("product_id")
                    quantity = item.get("quantity", 1)
                    self.inventory[product_id] = self.inventory.get(product_id, 0) + quantity

                del self.reservations[order_id]
                logger.info(f"Inventory released for order {order_id}")

    async def run(self):
        """Run the service"""
        self.setup_handlers()
        await self.client.start(host="0.0.0.0", port=8003)


async def main():
    """Main entry point"""
    service = InventoryService()

    print("Inventory Service")
    print("=" * 50)
    print("This service will:")
    print("1. Connect to event bus at http://localhost:8000")
    print("2. Listen on http://localhost:8003")
    print("3. Subscribe to inventory.reserve topic")
    print("4. Publish inventory.reserved events")
    print("=" * 50)

    try:
        await service.run()
    except KeyboardInterrupt:
        print("\nService stopped")
        await service.client.stop()


if __name__ == "__main__":
    asyncio.run(main())
