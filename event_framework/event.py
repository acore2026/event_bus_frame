"""事件定义模块"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Optional, Callable
from enum import Enum


class EventStatus(Enum):
    """事件状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class EventMetadata:
    """事件元数据"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = field(default="unknown")
    version: str = field(default="1.0")
    correlation_id: Optional[str] = None
    retry_count: int = 0
    status: str = field(default=EventStatus.PENDING.value)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventMetadata":
        return cls(**data)


@dataclass
class Event:
    """
    事件基类

    Attributes:
        event_type: 事件类型，用于路由（如：user.created, order.completed）
        payload: 事件数据负载
        metadata: 事件元数据
    """
    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self):
        if not self.event_type:
            raise ValueError("event_type cannot be empty")

    def to_json(self) -> str:
        """序列化为 JSON"""
        return json.dumps({
            "event_type": self.event_type,
            "payload": self.payload,
            "metadata": self.metadata.to_dict()
        }, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "Event":
        """从 JSON 反序列化"""
        data = json.loads(json_str)
        return cls(
            event_type=data["event_type"],
            payload=data.get("payload", {}),
            metadata=EventMetadata.from_dict(data.get("metadata", {}))
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type,
            "payload": self.payload,
            "metadata": self.metadata.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """从字典创建"""
        return cls(
            event_type=data["event_type"],
            payload=data.get("payload", {}),
            metadata=EventMetadata.from_dict(data.get("metadata", {}))
        )

    def set_correlation_id(self, correlation_id: str) -> "Event":
        """设置关联 ID"""
        self.metadata.correlation_id = correlation_id
        return self

    def with_source(self, source: str) -> "Event":
        """设置事件来源"""
        self.metadata.source = source
        return self


# 事件处理器类型
EventHandler = Callable[[Event], None]
