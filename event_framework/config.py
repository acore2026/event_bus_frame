"""框架配置模块"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EventConfig:
    """事件框架配置"""

    # RabbitMQ 连接配置
    host: str = "localhost"
    port: int = 5672
    username: str = "guest"
    password: str = "guest"
    virtual_host: str = "/"

    # 连接池配置
    connection_timeout: int = 30
    heartbeat: int = 600
    max_retries: int = 3
    retry_delay: float = 1.0

    # 消息配置
    exchange_type: str = "topic"
    delivery_mode: int = 2  # 2 = 持久化
    content_type: str = "application/json"

    # 消费者配置
    prefetch_count: int = 10
    auto_ack: bool = False

    @property
    def connection_url(self) -> str:
        """生成连接 URL"""
        return (
            f"amqp://{self.username}:{self.password}@"
            f"{self.host}:{self.port}{self.virtual_host}"
        )

    @classmethod
    def from_env(cls) -> "EventConfig":
        """从环境变量加载配置"""
        import os

        return cls(
            host=os.getenv("RABBITMQ_HOST", "localhost"),
            port=int(os.getenv("RABBITMQ_PORT", "5672")),
            username=os.getenv("RABBITMQ_USER", "guest"),
            password=os.getenv("RABBITMQ_PASS", "guest"),
            virtual_host=os.getenv("RABBITMQ_VHOST", "/"),
        )
