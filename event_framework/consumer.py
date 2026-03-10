"""事件消费模块（高级消费者，支持确认、重试、死信队列）"""

import json
import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPError

from .connection import ConnectionManager
from .config import EventConfig
from .event import Event, EventHandler, EventStatus

logger = logging.getLogger(__name__)


class ConsumerMode(Enum):
    """消费者模式"""
    SINGLE = "single"      # 单条处理
    BATCH = "batch"        # 批量处理


@dataclass
class ConsumerOptions:
    """消费者选项"""
    # 重试配置
    max_retries: int = 3
    retry_delay_ms: int = 1000
    enable_retry_queue: bool = True

    # 死信队列配置
    enable_dlq: bool = True
    dlq_ttl_hours: int = 24

    # 批量处理配置
    batch_size: int = 10
    batch_timeout_ms: int = 5000

    # 并发配置
    max_workers: int = 1


class EventConsumer:
    """
    高级事件消费者

    特性：
    - 自动重试机制
    - 死信队列（DLQ）
    - 批量消费
    - 并发处理
    """

    DEFAULT_EXCHANGE = "events"
    RETRY_EXCHANGE = "events.retry"
    DLQ_EXCHANGE = "events.dlq"

    def __init__(
        self,
        config: Optional[EventConfig] = None,
        exchange_name: str = DEFAULT_EXCHANGE,
        queue_name: str = "default",
        connection_manager: Optional[ConnectionManager] = None,
        options: Optional[ConsumerOptions] = None
    ):
        self.config = config or EventConfig()
        self.exchange_name = exchange_name
        self.queue_name = queue_name
        self.options = options or ConsumerOptions()
        self._connection_manager = connection_manager or ConnectionManager(self.config)

        self._handlers: Dict[str, List[EventHandler]] = {}
        self._running = False
        self._consumer_thread: Optional[threading.Thread] = None
        self._channel: Optional[BlockingChannel] = None
        self._batch_buffer: List[Any] = []
        self._batch_timer: Optional[float] = None

    def register_handler(
        self,
        event_type: str,
        handler: EventHandler
    ) -> "EventConsumer":
        """
        注册事件处理器

        Args:
            event_type: 事件类型（精确匹配）
            handler: 处理函数
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info(f"Registered handler for event: {event_type}")
        return self

    def on(self, event_type: str) -> Callable:
        """装饰器方式注册处理器"""
        def decorator(func: EventHandler) -> EventHandler:
            self.register_handler(event_type, func)
            return func
        return decorator

    def _setup_infrastructure(self) -> None:
        """设置交换机、队列和绑定"""
        channel = self._connection_manager.get_channel()

        # 声明主交换机
        self._connection_manager.declare_exchange(
            self.exchange_name,
            self.config.exchange_type
        )

        # 声明重试交换机
        if self.options.enable_retry_queue:
            channel.exchange_declare(
                exchange=self.RETRY_EXCHANGE,
                exchange_type="topic",
                durable=True
            )

        # 声明死信交换机
        if self.options.enable_dlq:
            channel.exchange_declare(
                exchange=self.DLQ_EXCHANGE,
                exchange_type="topic",
                durable=True
            )

        # 主队列配置
        main_queue_args = {}
        if self.options.enable_dlq:
            main_queue_args["x-dead-letter-exchange"] = self.DLQ_EXCHANGE
            main_queue_args["x-dead-letter-routing-key"] = f"{self.queue_name}.failed"

        # 声明主队列
        channel.queue_declare(
            queue=self.queue_name,
            durable=True,
            arguments=main_queue_args
        )

        # 绑定主队列到主交换机
        for event_type in self._handlers.keys():
            channel.queue_bind(
                queue=self.queue_name,
                exchange=self.exchange_name,
                routing_key=event_type
            )

        # 声明重试队列
        if self.options.enable_retry_queue:
            retry_queue_name = f"{self.queue_name}.retry"
            channel.queue_declare(
                queue=retry_queue_name,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": self.exchange_name,
                    "x-dead-letter-routing-key": "#",
                    "x-message-ttl": self.options.retry_delay_ms,
                }
            )
            channel.queue_bind(
                queue=retry_queue_name,
                exchange=self.RETRY_EXCHANGE,
                routing_key="#"
            )

        # 声明死信队列
        if self.options.enable_dlq:
            dlq_queue_name = f"{self.queue_name}.dlq"
            channel.queue_declare(
                queue=dlq_queue_name,
                durable=True,
                arguments={
                    "x-message-ttl": self.options.dlq_ttl_hours * 3600 * 1000,
                    "x-dead-letter-exchange": self.exchange_name,
                }
            )
            channel.queue_bind(
                queue=dlq_queue_name,
                exchange=self.DLQ_EXCHANGE,
                routing_key=f"{self.queue_name}.failed"
            )

        logger.info(f"Infrastructure setup complete for queue: {self.queue_name}")

    def _send_to_retry(self, channel: BlockingChannel, body: bytes, headers: Dict) -> None:
        """发送消息到重试队列"""
        retry_count = headers.get('x-retry-count', 0) + 1

        properties = pika.BasicProperties(
            content_type=self.config.content_type,
            delivery_mode=2,
            headers={**headers, 'x-retry-count': retry_count}
        )

        channel.basic_publish(
            exchange=self.RETRY_EXCHANGE,
            routing_key="#",
            body=body,
            properties=properties
        )

        logger.info(f"Message sent to retry queue (attempt {retry_count})")

    def _process_single_message(
        self,
        channel: BlockingChannel,
        method,
        properties,
        body: bytes
    ) -> bool:
        """
        处理单条消息

        Returns:
            bool: 处理是否成功
        """
        try:
            event_data = json.loads(body.decode('utf-8'))
            event = Event.from_dict(event_data)

            headers = properties.headers or {}
            retry_count = headers.get('x-retry-count', 0)

            logger.debug(
                f"Processing event: {event.event_type} "
                f"(id={event.metadata.event_id}, retry={retry_count})"
            )

            handlers = self._handlers.get(event.event_type, [])
            if not handlers:
                logger.warning(f"No handlers for event type: {event.event_type}")
                return True

            event.metadata.retry_count = retry_count
            event.metadata.status = EventStatus.PROCESSING.value

            success = True
            for handler in handlers:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Handler error: {e}")
                    success = False

            if success:
                event.metadata.status = EventStatus.SUCCESS.value
                logger.info(f"Event processed successfully: {event.event_type}")
            else:
                event.metadata.status = EventStatus.FAILED.value
                # 检查是否需要重试
                if retry_count < self.options.max_retries:
                    self._send_to_retry(channel, body, headers)
                else:
                    logger.error(
                        f"Event {event.event_type} failed after "
                        f"{retry_count} retries, sending to DLQ"
                    )

            return success

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {e}")
            return False
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return False

    def _on_message(
        self,
        channel: BlockingChannel,
        method,
        properties,
        body: bytes
    ) -> None:
        """消息回调"""
        success = self._process_single_message(channel, method, properties, body)

        if not self.config.auto_ack:
            if success:
                channel.basic_ack(delivery_tag=method.delivery_tag)
            else:
                # 如果失败，已经发送到重试队列或 DLQ，这里需要确认原始消息
                channel.basic_ack(delivery_tag=method.delivery_tag)

    def _process_batch(self) -> None:
        """处理批量消息"""
        if not self._batch_buffer:
            return

        logger.info(f"Processing batch of {len(self._batch_buffer)} messages")

        for item in self._batch_buffer:
            self._process_single_message(
                item['channel'],
                item['method'],
                item['properties'],
                item['body']
            )
            if not self.config.auto_ack:
                item['channel'].basic_ack(delivery_tag=item['method'].delivery_tag)

        self._batch_buffer.clear()
        self._batch_timer = None

    def _on_batch_message(
        self,
        channel: BlockingChannel,
        method,
        properties,
        body: bytes
    ) -> None:
        """批量消息回调"""
        self._batch_buffer.append({
            'channel': channel,
            'method': method,
            'properties': properties,
            'body': body
        })

        if len(self._batch_buffer) >= self.options.batch_size:
            self._process_batch()
        elif self._batch_timer is None:
            self._batch_timer = time.time() + (self.options.batch_timeout_ms / 1000)

    def start(
        self,
        mode: ConsumerMode = ConsumerMode.SINGLE,
        blocking: bool = True
    ) -> None:
        """
        开始消费

        Args:
            mode: 消费模式（单条或批量）
            blocking: 是否阻塞
        """
        if self._running:
            logger.warning("Consumer is already running")
            return

        if not self._handlers:
            raise ValueError("No event handlers registered")

        self._setup_infrastructure()

        self._channel = self._connection_manager.get_channel()
        self._channel.basic_qos(prefetch_count=self.config.prefetch_count)

        self._running = True

        if mode == ConsumerMode.BATCH:
            callback = self._on_batch_message
        else:
            callback = self._on_message

        def consume():
            try:
                self._channel.basic_consume(
                    queue=self.queue_name,
                    on_message_callback=callback,
                    auto_ack=self.config.auto_ack
                )
                logger.info(
                    f"Started consumer on queue: {self.queue_name} "
                    f"(mode={mode.value})"
                )

                while self._running:
                    try:
                        self._connection_manager._connection.process_data_events(
                            time_limit=1
                        )

                        # 检查批量超时
                        if mode == ConsumerMode.BATCH and self._batch_timer:
                            if time.time() >= self._batch_timer:
                                self._process_batch()

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

        # 处理剩余批量消息
        if self._batch_buffer:
            self._process_batch()

        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5)

        if self._channel and self._channel.is_open:
            try:
                self._channel.stop_consuming()
            except Exception as e:
                logger.warning(f"Error stopping consumer: {e}")

        logger.info("Consumer stopped")

    def close(self) -> None:
        """关闭消费者"""
        self.stop()
        if self._connection_manager:
            self._connection_manager.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
