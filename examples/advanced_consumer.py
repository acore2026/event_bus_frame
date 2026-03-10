"""
高级消费者示例
展示重试机制、死信队列和批量消费
"""

import random
import logging
from event_framework import (
    EventConsumer, EventPublisher, Event,
    EventConfig, ConsumerOptions, ConsumerMode
)

logging.basicConfig(level=logging.INFO)


def example_consumer_with_retry():
    """带重试机制的消费者"""
    print("=== Consumer with Retry Example ===")

    config = EventConfig(host="localhost")

    # 配置消费者选项
    options = ConsumerOptions(
        max_retries=3,
        retry_delay_ms=5000,  # 5秒后重试
        enable_retry_queue=True,
        enable_dlq=True,
        dlq_ttl_hours=24
    )

    consumer = EventConsumer(
        config=config,
        queue_name="payment-queue",
        options=options
    )

    fail_count = 0

    @consumer.on("payment.process")
    def process_payment(event):
        nonlocal fail_count
        print(f"Processing payment: {event.payload}")

        # 模拟随机失败
        if random.random() < 0.7:  # 70% 失败率
            fail_count += 1
            print(f"Payment processing failed (attempt will be retried)")
            raise Exception("Payment gateway error")

        print("Payment processed successfully!")

    print("Starting consumer with retry mechanism...")
    try:
        consumer.start(mode=ConsumerMode.SINGLE, blocking=True)
    except KeyboardInterrupt:
        consumer.stop()


def example_batch_consumer():
    """批量消费示例"""
    print("=== Batch Consumer Example ===")

    config = EventConfig(host="localhost")

    options = ConsumerOptions(
        batch_size=5,
        batch_timeout_ms=3000,  # 3秒超时
    )

    consumer = EventConsumer(
        config=config,
        queue_name="log-queue",
        options=options
    )

    @consumer.on("log.record")
    def process_log(event):
        print(f"Processing log: {event.payload}")

    print("Starting batch consumer...")
    try:
        consumer.start(mode=ConsumerMode.BATCH, blocking=True)
    except KeyboardInterrupt:
        consumer.stop()


def example_multiple_handlers():
    """多个处理器示例"""
    print("=== Multiple Handlers Example ===")

    config = EventConfig(host="localhost")

    consumer = EventConsumer(
        config=config,
        queue_name="analytics-queue"
    )

    @consumer.on("user.signup")
    def track_signup(event):
        print(f"[Analytics] User signup tracked: {event.payload.get('user_id')}")

    @consumer.on("user.signup")
    def send_welcome_email(event):
        print(f"[Email] Sending welcome email to: {event.payload.get('email')}")

    @consumer.on("user.signup")
    def notify_admin(event):
        print(f"[Admin] New user signup: {event.payload.get('username')}")

    print("Starting consumer with multiple handlers...")
    try:
        consumer.start(blocking=True)
    except KeyboardInterrupt:
        consumer.stop()


def test_retry_mechanism():
    """测试重试机制"""
    print("=== Testing Retry Mechanism ===")

    config = EventConfig(host="localhost")

    # 先发布测试事件
    with EventPublisher(config=config) as publisher:
        for i in range(5):
            event = Event(
                event_type="payment.process",
                payload={
                    "payment_id": f"PAY-{i}",
                    "amount": 100.0 * (i + 1)
                }
            ).with_source("test")
            publisher.publish(event)
            print(f"Published payment event {i}")

    # 然后启动消费者
    example_consumer_with_retry()


if __name__ == "__main__":
    import sys

    examples = {
        "retry": example_consumer_with_retry,
        "batch": example_batch_consumer,
        "multi": example_multiple_handlers,
        "test": test_retry_mechanism,
    }

    if len(sys.argv) < 2:
        print("Usage: python advanced_consumer.py [retry|batch|multi|test]")
        print("\nAvailable examples:")
        for name in examples:
            print(f"  - {name}")
        sys.exit(1)

    command = sys.argv[1]
    if command in examples:
        examples[command]()
    else:
        print(f"Unknown command: {command}")
