"""
基础使用示例
展示如何发布和订阅事件
"""

import time
import logging
from event_framework import (
    EventPublisher, EventSubscriber, Event,
    EventConfig, ConnectionManager
)

# 配置日志
logging.basicConfig(level=logging.INFO)


def example_basic_publish():
    """基础发布示例"""
    print("=== Basic Publish Example ===")

    # 创建配置
    config = EventConfig(
        host="localhost",
        port=5672,
        username="guest",
        password="guest"
    )

    # 创建发布器
    with EventPublisher(config=config) as publisher:
        # 创建事件
        event = Event(
            event_type="user.created",
            payload={
                "user_id": "12345",
                "username": "john_doe",
                "email": "john@example.com"
            }
        ).with_source("user-service")

        # 发布事件
        success = publisher.publish(event)
        print(f"Event published: {success}")

        # 使用便捷方法发布
        publisher.publish_sync(
            event_type="order.completed",
            payload={"order_id": "ORD-001", "amount": 99.99},
            source="order-service"
        )


def example_subscriber():
    """订阅者示例"""
    print("=== Subscriber Example ===")

    config = EventConfig(host="localhost")

    # 创建订阅器
    subscriber = EventSubscriber(
        config=config,
        queue_name="user-service-queue"
    )

    # 使用装饰器订阅事件
    @subscriber.on("user.created")
    def handle_user_created(event):
        print(f"[Handler] User created: {event.payload}")

    @subscriber.on("user.*")  # 使用通配符订阅 user.created, user.updated 等
    def handle_user_events(event):
        print(f"[Handler] User event ({event.event_type}): {event.payload}")

    @subscriber.on("order.#")  # 订阅所有 order 相关事件
    def handle_order_events(event):
        print(f"[Handler] Order event: {event.event_type}")

    # 开始消费（阻塞模式）
    print("Waiting for events... (Press Ctrl+C to stop)")
    try:
        subscriber.start(blocking=True)
    except KeyboardInterrupt:
        subscriber.stop()


def example_async_subscriber():
    """异步订阅示例"""
    print("=== Async Subscriber Example ===")

    config = EventConfig(host="localhost")

    subscriber = EventSubscriber(
        config=config,
        queue_name="notification-queue"
    )

    @subscriber.on("notification.send")
    def send_notification(event):
        notification_type = event.payload.get("type")
        message = event.payload.get("message")
        print(f"Sending {notification_type} notification: {message}")

    # 非阻塞模式
    subscriber.start(blocking=False)

    # 主程序继续执行其他任务
    print("Subscriber running in background...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        subscriber.stop()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python basic_usage.py [publish|subscribe|async]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "publish":
        example_basic_publish()
    elif command == "subscribe":
        example_subscriber()
    elif command == "async":
        example_async_subscriber()
    else:
        print(f"Unknown command: {command}")
