"""
Configuration for Event Bus Framework
"""

from pydantic_settings import BaseSettings
from typing import List, Optional


class EventBusConfig(BaseSettings):
    """Event Bus Server Configuration"""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000

    # Subscription management
    heartbeat_interval: int = 30  # seconds
    subscription_timeout: int = 120  # seconds before considering subscriber dead
    cleanup_interval: int = 60  # seconds between cleanup runs

    # Delivery settings
    max_retries: int = 3
    retry_interval: int = 5  # seconds between retries
    request_timeout: int = 30  # seconds

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Optional: Redis for persistence
    redis_url: Optional[str] = None

    # Optional: Authentication
    api_key: Optional[str] = None
    jwt_secret: Optional[str] = None

    class Config:
        env_prefix = "EVENT_BUS_"
        env_file = ".env"


class ClientConfig(BaseSettings):
    """Event Bus Client Configuration"""

    # Service identification
    service_name: str = "unnamed-service"
    service_url: str = "http://localhost:8001"

    # Event Bus connection
    event_bus_url: str = "http://localhost:8000"

    # Heartbeat
    heartbeat_interval: int = 30
    auto_reconnect: bool = True

    # Retry policy
    max_retries: int = 3
    retry_interval: int = 5
    request_timeout: int = 30

    class Config:
        env_prefix = "EVENT_CLIENT_"
        env_file = ".env"


def get_server_config() -> EventBusConfig:
    """Get server configuration"""
    return EventBusConfig()


def get_client_config() -> ClientConfig:
    """Get client configuration"""
    return ClientConfig()
