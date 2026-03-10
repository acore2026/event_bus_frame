"""RabbitMQ 连接管理模块"""

import logging
import threading
import time
from typing import Optional, Callable

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPConnectionError, ChannelClosed

from .config import EventConfig

logger = logging.getLogger(__name__)


class ConnectionManager:
    """RabbitMQ 连接管理器（单例模式）"""

    _instance: Optional["ConnectionManager"] = None
    _lock = threading.Lock()

    def __new__(cls, config: Optional[EventConfig] = None) -> "ConnectionManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[EventConfig] = None):
        if self._initialized:
            return

        self.config = config or EventConfig()
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Optional[BlockingChannel] = None
        self._lock = threading.RLock()
        self._initialized = True
        self._closed = False

    def connect(self) -> pika.BlockingConnection:
        """建立连接"""
        with self._lock:
            if self._connection and self._connection.is_open:
                return self._connection

            credentials = pika.PlainCredentials(
                self.config.username,
                self.config.password
            )
            parameters = pika.ConnectionParameters(
                host=self.config.host,
                port=self.config.port,
                virtual_host=self.config.virtual_host,
                credentials=credentials,
                connection_attempts=self.config.max_retries,
                retry_delay=self.config.retry_delay,
                heartbeat=self.config.heartbeat,
                blocked_connection_timeout=self.config.connection_timeout,
            )

            for attempt in range(self.config.max_retries):
                try:
                    logger.info(f"Connecting to RabbitMQ (attempt {attempt + 1})...")
                    self._connection = pika.BlockingConnection(parameters)
                    logger.info("Connected to RabbitMQ successfully")
                    return self._connection
                except AMQPConnectionError as e:
                    logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                    if attempt < self.config.max_retries - 1:
                        time.sleep(self.config.retry_delay)
                    else:
                        raise

            raise AMQPConnectionError("Failed to connect to RabbitMQ after all retries")

    def get_channel(self) -> BlockingChannel:
        """获取信道"""
        with self._lock:
            if self._channel and self._channel.is_open:
                return self._channel

            connection = self.connect()
            self._channel = connection.channel()
            return self._channel

    def declare_exchange(self, exchange_name: str, exchange_type: str = "topic") -> None:
        """声明交换机"""
        channel = self.get_channel()
        channel.exchange_declare(
            exchange=exchange_name,
            exchange_type=exchange_type,
            durable=True,
            auto_delete=False
        )
        logger.debug(f"Exchange declared: {exchange_name} ({exchange_type})")

    def declare_queue(self, queue_name: str, **kwargs) -> None:
        """声明队列"""
        channel = self.get_channel()
        channel.queue_declare(queue=queue_name, durable=True, **kwargs)
        logger.debug(f"Queue declared: {queue_name}")

    def bind_queue(self, queue_name: str, exchange_name: str, routing_key: str) -> None:
        """绑定队列到交换机"""
        channel = self.get_channel()
        channel.queue_bind(
            queue=queue_name,
            exchange=exchange_name,
            routing_key=routing_key
        )
        logger.debug(f"Queue bound: {queue_name} -> {exchange_name} ({routing_key})")

    def close(self) -> None:
        """关闭连接"""
        with self._lock:
            self._closed = True
            if self._channel and self._channel.is_open:
                try:
                    self._channel.close()
                except Exception as e:
                    logger.warning(f"Error closing channel: {e}")

            if self._connection and self._connection.is_open:
                try:
                    self._connection.close()
                    logger.info("RabbitMQ connection closed")
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")

            self._channel = None
            self._connection = None
            ConnectionManager._instance = None

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return (
            self._connection is not None
            and self._connection.is_open
            and self._channel is not None
            and self._channel.is_open
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
