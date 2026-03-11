"""
Example Payment Service - Handles payment processing

This service:
1. Subscribes to order.created events
2. Processes payments
3. Publishes payment.completed events
"""

import asyncio
import logging
import random
from event_bus import EventBusClient, Event, EventType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("payment_service")


class PaymentService:
    """Example payment processing service"""

    def __init__(self):
        self.client = EventBusClient(
            service_name="payment-service",
            service_url="http://localhost:8002",
            event_bus_url="http://localhost:8000",
            event_types=[EventType.TOPIC],
            topics=["order.created"]
        )
        self.payments = {}

    def setup_handlers(self):
        """Setup event handlers"""

        @self.client.handler.on_topic("order.created")
        async def handle_order_created(event: Event):
            """Process payment for new orders"""
            order = event.payload
            order_id = order.get("id")

            logger.info(f"Processing payment for order: {order_id}")

            # Simulate payment processing
            await asyncio.sleep(random.uniform(0.5, 2.0))

            # Simulate success/failure
            success = random.random() > 0.2  # 80% success rate

            payment = {
                "order_id": order_id,
                "amount": sum(item.get("quantity", 1) * 10 for item in order.get("items", [])),
                "status": "completed" if success else "failed",
                "transaction_id": f"TXN-{len(self.payments) + 1:06d}"
            }

            self.payments[order_id] = payment

            # Publish payment completion
            await self.client.publish_topic(
                topic="payment.completed",
                payload=payment,
                priority=3  # HIGH
            )

            logger.info(f"Payment {payment['status']} for order {order_id}")

    async def run(self):
        """Run the service"""
        self.setup_handlers()
        await self.client.start(host="0.0.0.0", port=8002)


async def main():
    """Main entry point"""
    service = PaymentService()

    print("Payment Service")
    print("=" * 50)
    print("This service will:")
    print("1. Connect to event bus at http://localhost:8000")
    print("2. Listen on http://localhost:8002")
    print("3. Subscribe to order.created topic")
    print("4. Publish payment.completed events")
    print("=" * 50)

    try:
        await service.run()
    except KeyboardInterrupt:
        print("\nService stopped")
        await service.client.stop()


if __name__ == "__main__":
    asyncio.run(main())
