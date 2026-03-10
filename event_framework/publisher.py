"""事件发布模块"""

import json
import logging
import time
from typing import Optional, Dict, Any

import pika
from pika.exceptions import AMQPError

from .connection import ConnectionManager
from .config import EventConfig
from .event import Event

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    事件发布器

    用于向 RabbitMQ 发布事件
    """

    DEFAULT_EXCHANGE = "events"

    def __init__(
        self,
        config: Optional[EventConfig] = None,
        exchange_name: str = DEFAULT_EXCHANGE,
        connection_manager: Optional[ConnectionManager] = None
    ):
        self.config = config or EventConfig()
        self.exchange_name = exchange_name
        self._connection_manager = connection_manager or ConnectionManager(self.config)
        self._initialize()

    def _initialize(self) -> None:
        """初始化交换机和连接"""
        try:
            self._connection_manager.declare_exchange(
                self.exchange_name,
                self.config.exchange_type
            )
        except AMQPError as e:
            logger.error(f"Failed to initialize publisher: {e}")
            raise

    def publish(
        self,
        event: Event,
        routing_key: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        发布事件

        Args:
            event: 要发布的事件
            routing_key: 路由键，默认为 event.event_type
            headers: 额外的消息头

        Returns:
            bool: 是否发布成功
        """
        try:
            channel = self._connection_manager.get_channel()

            # 使用 event_type 作为默认路由键
            routing_key = routing_key or event.event_type

            # 构建消息属性
            properties = pika.BasicProperties(
                content_type=self.config.content_type,
                delivery_mode=self.config.delivery_mode,
                message_id=event.metadata.event_id,
                timestamp=int(time.time()),
                headers=headers or {},
                correlation_id=event.metadata.correlation_id,
            )

            # 发布消息
            channel.basic_publish(
                exchange=self.exchange_name,
                routing_key=routing_key,
                body=event.to_json().encode('utf-8'),
                properties=properties
            )

            logger.info(
                f"Event published: {event.event_type} "
                f"(id={event.metadata.event_id}, routing_key={routing_key})"
            )
            return True

        except AMQPError as e:
            logger.error(f"Failed to publish event {event.event_type}: {e}")
            return False

    def publish_sync(
        self,
        event_type: str,
        payload: Dict[str, Any],
        source: str = "unknown",
        routing_key: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        同步发布事件（便捷方法）

        Args:
            event_type: 事件类型
            payload: 事件数据
            source: 事件来源
            routing_key: 路由键
            correlation_id: 关联 ID

        Returns:
            bool: 是否发布成功
        """
        event = Event(
            event_type=event_type,
            payload=payload
        ).with_source(source)

        if correlation_id:
            event.set_correlation_id(correlation_id)

        return self.publish(event, routing_key)

    def close(self) -> None:
        """关闭发布器"""
        if self._connection_manager:
            self._connection_manager.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
