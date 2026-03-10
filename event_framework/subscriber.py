"""事件订阅模块"""

import json
import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Set
from functools import wraps

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPError

from .connection import ConnectionManager
from .config import EventConfig
from .event import Event, EventHandler, EventStatus

logger = logging.getLogger(__name__)


class EventSubscriber:
    """
    事件订阅器

    用于订阅特定类型的事件，支持基于路由键的订阅模式
    """

    DEFAULT_EXCHANGE = "events"

    def __init__(
        self,
        config: Optional[EventConfig] = None,
        exchange_name: str = DEFAULT_EXCHANGE,
        connection_manager: Optional[ConnectionManager] = None,
        queue_name: Optional[str] = None
    ):
        self.config = config or EventConfig()
        self.exchange_name = exchange_name
        self.queue_name = queue_name
        self._connection_manager = connection_manager or ConnectionManager(self.config)
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._running = False
        self._consumer_thread: Optional[threading.Thread] = None
        self._channel: Optional[BlockingChannel] = None

    def subscribe(self, event_pattern: str, handler: EventHandler) -> "EventSubscriber":
        """
        订阅事件

        Args:
            event_pattern: 事件模式，支持通配符 * 和 #
                - * 匹配一个单词（如：user.* 匹配 user.created, user.deleted）
                - # 匹配零个或多个单词（如：user.# 匹配 user, user.created, user.order.completed）
            handler: 事件处理函数

        Returns:
            self，支持链式调用
        """
        if event_pattern not in self._handlers:
            self._handlers[event_pattern] = []
        self._handlers[event_pattern].append(handler)
        logger.info(f"Subscribed to event pattern: {event_pattern}")
        return self

    def on(self, event_pattern: str) -> Callable:
        """
        装饰器方式订阅事件

        Example:
            @subscriber.on("user.created")
            def handle_user_created(event):
                print(f"User created: {event.payload}")
        """
        def decorator(func: EventHandler) -> EventHandler:
            self.subscribe(event_pattern, func)
            @wraps(func)
            def wrapper(event: Event) -> None:
                return func(event)
            return wrapper
        return decorator

    def _setup_bindings(self) -> None:
        """设置队列绑定"""
        # 声明交换机
        self._connection_manager.declare_exchange(
            self.exchange_name,
            self.config.exchange_type
        )

        # 声明队列
        if self.queue_name:
            self._connection_manager.declare_queue(self.queue_name)
        else:
            # 使用临时队列
            self.queue_name = self._connection_manager.get_channel().queue_declare(
                queue='',
                exclusive=True,
                auto_delete=True
            ).method.queue
            logger.info(f"Created temporary queue: {self.queue_name}")

        # 绑定队列到交换机
        for pattern in self._handlers.keys():
            self._connection_manager.bind_queue(
                self.queue_name,
                self.exchange_name,
                pattern
            )

    def _process_message(
        self,
        channel: BlockingChannel,
        method,
        properties,
        body: bytes
    ) -> None:
        """处理接收到的消息"""
        try:
            # 解析事件
            event_data = json.loads(body.decode('utf-8'))
            event = Event.from_dict(event_data)

            logger.info(
                f"Received event: {event.event_type} "
                f"(id={event.metadata.event_id}, routing_key={method.routing_key})"
            )

            # 找到匹配的处理器
            handlers_called = 0
            for pattern, handlers in self._handlers.items():
                if self._match_pattern(method.routing_key, pattern):
                    for handler in handlers:
                        try:
                            event.metadata.status = EventStatus.PROCESSING.value
                            handler(event)
                            event.metadata.status = EventStatus.SUCCESS.value
                            handlers_called += 1
                        except Exception as e:
                            logger.error(f"Handler error for {event.event_type}: {e}")
                            event.metadata.status = EventStatus.FAILED.value

            # 确认消息
            if not self.config.auto_ack:
                channel.basic_ack(delivery_tag=method.delivery_tag)

            logger.debug(f"Event processed: {event.event_type} ({handlers_called} handlers)")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {e}")
            if not self.config.auto_ack:
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            if not self.config.auto_ack:
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def _match_pattern(self, routing_key: str, pattern: str) -> bool:
        """
        检查路由键是否匹配模式

        支持 * 和 # 通配符
        """
        if pattern == routing_key:
            return True

        key_parts = routing_key.split('.')
        pattern_parts = pattern.split('.')

        key_idx = 0
        pattern_idx = 0

        while key_idx < len(key_parts) and pattern_idx < len(pattern_parts):
            if pattern_parts[pattern_idx] == '#':
                # # 匹配零个或多个单词
                if pattern_idx == len(pattern_parts) - 1:
                    return True
                # 尝试匹配 # 后面的部分
                next_pattern = pattern_parts[pattern_idx + 1]
                while key_idx < len(key_parts):
                    if key_parts[key_idx] == next_pattern:
                        pattern_idx += 2
                        key_idx += 1
                        break
                    key_idx += 1
                else:
                    return False
            elif pattern_parts[pattern_idx] == '*':
                # * 匹配一个单词
                key_idx += 1
                pattern_idx += 1
            else:
                if pattern_parts[pattern_idx] != key_parts[key_idx]:
                    return False
                key_idx += 1
                pattern_idx += 1

        return key_idx == len(key_parts) and pattern_idx == len(pattern_parts)

    def start(self, blocking: bool = True) -> None:
        """
        开始消费事件

        Args:
            blocking: 是否阻塞当前线程
        """
        if self._running:
            logger.warning("Subscriber is already running")
            return

        if not self._handlers:
            raise ValueError("No event handlers registered")

        self._setup_bindings()

        self._channel = self._connection_manager.get_channel()
        self._channel.basic_qos(prefetch_count=self.config.prefetch_count)

        self._running = True

        def consume():
            try:
                self._channel.basic_consume(
                    queue=self.queue_name,
                    on_message_callback=self._process_message,
                    auto_ack=self.config.auto_ack
                )
                logger.info(f"Started consuming from queue: {self.queue_name}")
                while self._running:
                    try:
                        self._connection_manager._connection.process_data_events(time_limit=1)
                    except Exception as e:
                        if self._running:
                            logger.error(f"Consumer error: {e}")
                            time.sleep(1)
            except Exception as e:
                logger.error(f"Consumer thread error: {e}")
            finally:
                self._running = False

        if blocking:
            consume()
        else:
            self._consumer_thread = threading.Thread(target=consume, daemon=True)
            self._consumer_thread.start()

    def stop(self) -> None:
        """停止消费"""
        self._running = False
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5)
        if self._channel and self._channel.is_open:
            try:
                self._channel.stop_consuming()
            except Exception as e:
                logger.warning(f"Error stopping consumer: {e}")
        logger.info("Subscriber stopped")

    def close(self) -> None:
        """关闭订阅器"""
        self.stop()
        if self._connection_manager:
            self._connection_manager.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
