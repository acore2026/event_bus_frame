"""
服务间通信示例
模拟订单服务和库存服务之间的通信
"""

import json
import time
import uuid
import logging
from threading import Thread
from event_framework import (
    EventPublisher, EventSubscriber, EventConsumer,
    Event, EventConfig, ConsumerOptions
)

logging.basicConfig(level=logging.INFO)


class OrderService:
    """订单服务"""

    def __init__(self):
        self.config = EventConfig(host="localhost")
        self.publisher = EventPublisher(config=self.config)
        self.subscriber = EventSubscriber(
            config=self.config,
            queue_name="order-service-queue"
        )
        self.orders = {}

    def create_order(self, user_id: str, items: list):
        """创建订单"""
        order_id = f"ORD-{uuid.uuid4().hex[:8]}"

        order = {
            "order_id": order_id,
            "user_id": user_id,
            "items": items,
            "status": "pending",
            "total": sum(item["price"] * item["quantity"] for item in items)
        }
        self.orders[order_id] = order

        # 发布订单创建事件
        event = Event(
            event_type="order.created",
            payload=order
        ).with_source("order-service")

        # 设置关联 ID 用于追踪
        correlation_id = str(uuid.uuid4())
        event.set_correlation_id(correlation_id)

        self.publisher.publish(event, routing_key="order.created")
        print(f"[OrderService] Order created: {order_id}")

        return order_id

    def handle_inventory_reserved(self, event):
        """处理库存预留成功事件"""
        order_id = event.payload.get("order_id")
        if order_id in self.orders:
            self.orders[order_id]["status"] = "confirmed"
            print(f"[OrderService] Order {order_id} confirmed (inventory reserved)")

            # 发布订单确认事件
            confirm_event = Event(
                event_type="order.confirmed",
                payload={
                    "order_id": order_id,
                    "user_id": self.orders[order_id]["user_id"],
                    "total": self.orders[order_id]["total"]
                }
            ).with_source("order-service")

            self.publisher.publish(confirm_event)

    def handle_inventory_failed(self, event):
        """处理库存预留失败事件"""
        order_id = event.payload.get("order_id")
        if order_id in self.orders:
            self.orders[order_id]["status"] = "cancelled"
            reason = event.payload.get("reason")
            print(f"[OrderService] Order {order_id} cancelled: {reason}")

    def start(self):
        """启动服务"""
        # 订阅库存相关事件
        self.subscriber.subscribe("inventory.reserved", self.handle_inventory_reserved)
        self.subscriber.subscribe("inventory.failed", self.handle_inventory_failed)

        # 在后台启动订阅
        self.subscriber.start(blocking=False)
        print("[OrderService] Started")

    def stop(self):
        self.subscriber.stop()
        self.publisher.close()


class InventoryService:
    """库存服务"""

    def __init__(self):
        self.config = EventConfig(host="localhost")
        self.publisher = EventPublisher(config=self.config)
        self.consumer = EventConsumer(
            config=self.config,
            queue_name="inventory-service-queue",
            options=ConsumerOptions(max_retries=2)
        )
        self.inventory = {
            "PROD-001": 100,
            "PROD-002": 50,
            "PROD-003": 0,  # 缺货
        }

    def handle_order_created(self, event):
        """处理订单创建事件"""
        order_id = event.payload.get("order_id")
        items = event.payload.get("items", [])

        print(f"[InventoryService] Checking inventory for order: {order_id}")

        # 检查库存
        for item in items:
            product_id = item.get("product_id")
            quantity = item.get("quantity", 0)

            available = self.inventory.get(product_id, 0)
            if available < quantity:
                # 库存不足
                fail_event = Event(
                    event_type="inventory.failed",
                    payload={
                        "order_id": order_id,
                        "product_id": product_id,
                        "requested": quantity,
                        "available": available,
                        "reason": f"Insufficient stock for {product_id}"
                    }
                ).with_source("inventory-service")

                self.publisher.publish(fail_event)
                return

        # 预留库存
        for item in items:
            product_id = item.get("product_id")
            quantity = item.get("quantity", 0)
            self.inventory[product_id] -= quantity

        # 发送预留成功事件
        reserved_event = Event(
            event_type="inventory.reserved",
            payload={
                "order_id": order_id,
                "items": items,
                "reserved_at": time.time()
            }
        ).with_source("inventory-service")

        self.publisher.publish(reserved_event)
        print(f"[InventoryService] Inventory reserved for order: {order_id}")

    def start(self):
        """启动服务"""
        self.consumer.register_handler("order.created", self.handle_order_created)
        self.consumer.start(blocking=False)
        print("[InventoryService] Started")

    def stop(self):
        self.consumer.stop()
        self.publisher.close()


class NotificationService:
    """通知服务"""

    def __init__(self):
        self.config = EventConfig(host="localhost")
        self.subscriber = EventSubscriber(
            config=self.config,
            queue_name="notification-service-queue"
        )

    def handle_order_confirmed(self, event):
        """处理订单确认事件，发送通知"""
        order_id = event.payload.get("order_id")
        user_id = event.payload.get("user_id")
        total = event.payload.get("total")

        print(f"[NotificationService] Sending confirmation to user {user_id}")
        print(f"  Order: {order_id}")
        print(f"  Total: ${total}")

    def start(self):
        self.subscriber.subscribe("order.confirmed", self.handle_order_confirmed)
        self.subscriber.start(blocking=False)
        print("[NotificationService] Started")

    def stop(self):
        self.subscriber.stop()


def run_demo():
    """运行完整演示"""
    print("=== Service Communication Demo ===\n")

    # 启动所有服务
    order_service = OrderService()
    inventory_service = InventoryService()
    notification_service = NotificationService()

    order_service.start()
    inventory_service.start()
    notification_service.start()

    time.sleep(1)  # 等待服务启动

    print("\n--- Creating Test Orders ---\n")

    # 测试场景 1：正常订单
    order_service.create_order(
        user_id="USER-001",
        items=[
            {"product_id": "PROD-001", "quantity": 2, "price": 50.0},
            {"product_id": "PROD-002", "quantity": 1, "price": 100.0}
        ]
    )

    time.sleep(2)

    # 测试场景 2：库存不足
    order_service.create_order(
        user_id="USER-002",
        items=[
            {"product_id": "PROD-003", "quantity": 1, "price": 200.0}
        ]
    )

    time.sleep(2)

    # 测试场景 3：多个商品，部分缺货
    order_service.create_order(
        user_id="USER-003",
        items=[
            {"product_id": "PROD-001", "quantity": 5, "price": 50.0},
            {"product_id": "PROD-003", "quantity": 1, "price": 200.0}
        ]
    )

    # 保持运行
    print("\n--- Press Ctrl+C to stop ---")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
        order_service.stop()
        inventory_service.stop()
        notification_service.stop()
        print("All services stopped")


if __name__ == "__main__":
    run_demo()
