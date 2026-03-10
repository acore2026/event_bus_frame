# RabbitMQ Event Framework

基于 RabbitMQ 的 Python 事件驱动框架，支持事件发布、订阅和消费。

## 特性

- **事件发布 (Publish)**：向指定路由键发布事件
- **事件订阅 (Subscribe)**：使用通配符模式订阅事件（支持 `*` 和 `#`）
- **事件消费 (Consume)**：高级消费者，支持重试、死信队列、批量消费
- **连接管理**：单例模式的连接管理器，自动重连
- **事件追踪**：内置事件 ID、关联 ID、重试计数等元数据

## 安装

```bash
pip install -r requirements.txt
```

依赖：
- pika >= 1.3.0
- pydantic >= 2.0.0

## 快速开始

### 1. 发布事件

```python
from event_framework import EventPublisher, Event, EventConfig

config = EventConfig(host="localhost", username="guest", password="guest")

with EventPublisher(config=config) as publisher:
    # 方式 1：使用 Event 对象
    event = Event(
        event_type="user.created",
        payload={"user_id": "123", "username": "john"}
    ).with_source("user-service")

    publisher.publish(event)

    # 方式 2：便捷方法
    publisher.publish_sync(
        event_type="order.completed",
        payload={"order_id": "ORD-001", "amount": 99.99},
        source="order-service"
    )
```

### 2. 订阅事件

```python
from event_framework import EventSubscriber, EventConfig

config = EventConfig(host="localhost")
subscriber = EventSubscriber(config=config, queue_name="my-queue")

# 使用装饰器订阅
@subscriber.on("user.created")
def handle_user_created(event):
    print(f"User created: {event.payload}")

@subscriber.on("user.*")  # 通配符匹配 user.created, user.updated 等
def handle_user_events(event):
    print(f"User event: {event.event_type}")

@subscriber.on("order.#")  # 匹配所有 order 相关事件
def handle_order_events(event):
    print(f"Order event: {event.payload}")

# 开始消费
subscriber.start(blocking=True)
```

### 3. 高级消费者

```python
from event_framework import (
    EventConsumer, EventConfig,
    ConsumerOptions, ConsumerMode
)

config = EventConfig(host="localhost")
options = ConsumerOptions(
    max_retries=3,
    retry_delay_ms=5000,
    enable_retry_queue=True,
    enable_dlq=True,
)

consumer = EventConsumer(
    config=config,
    queue_name="payment-queue",
    options=options
)

@consumer.on("payment.process")
def process_payment(event):
    # 如果抛出异常，会自动重试
    # 超过 max_retries 后进入死信队列
    result = process_payment_gateway(event.payload)
    return result

# 单条消费模式
consumer.start(mode=ConsumerMode.SINGLE, blocking=True)

# 或批量消费模式
# consumer.start(mode=ConsumerMode.BATCH, blocking=True)
```

## 路由模式

支持 RabbitMQ Topic 交换机的通配符规则：

- `*`：匹配一个单词（如 `user.*` 匹配 `user.created`, `user.updated`）
- `#`：匹配零个或多个单词（如 `order.#` 匹配 `order`, `order.created`, `order.items.updated`）

## 项目结构

```
event_framework/
├── __init__.py      # 框架入口
├── config.py        # 配置管理
├── connection.py    # 连接管理器
├── event.py         # 事件定义
├── publisher.py     # 事件发布器
├── subscriber.py    # 事件订阅器
└── consumer.py      # 高级消费者

examples/
├── basic_usage.py           # 基础使用示例
├── advanced_consumer.py     # 高级消费者示例
└── service_communication.py # 服务间通信示例
```

## 运行示例

确保 RabbitMQ 已运行：

```bash
# 使用 Docker 启动 RabbitMQ
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

运行示例：

```bash
# 基础发布示例
python examples/basic_usage.py publish

# 订阅示例
python examples/basic_usage.py subscribe

# 高级消费者示例
python examples/advanced_consumer.py retry
python examples/advanced_consumer.py batch

# 完整服务通信演示
python examples/service_communication.py
```

## 配置

### 代码配置

```python
from event_framework import EventConfig

config = EventConfig(
    host="localhost",
    port=5672,
    username="guest",
    password="guest",
    virtual_host="/",
    prefetch_count=10,
    max_retries=3,
)
```

### 环境变量配置

```python
from event_framework import EventConfig

# 自动从环境变量读取配置
config = EventConfig.from_env()
```

环境变量名：
- `RABBITMQ_HOST`
- `RABBITMQ_PORT`
- `RABBITMQ_USER`
- `RABBITMQ_PASS`
- `RABBITMQ_VHOST`

## 高级特性

### 事件元数据

```python
event = Event(
    event_type="user.created",
    payload={"user_id": "123"}
)

# 设置关联 ID（用于分布式追踪）
event.set_correlation_id("trace-123")

# 设置来源服务
event.with_source("user-service")

# 访问元数据
print(event.metadata.event_id)    # 自动生成的事件 ID
print(event.metadata.timestamp)   # 事件时间戳
print(event.metadata.retry_count) # 重试次数
```

### 批量消费

```python
from event_framework import ConsumerOptions, ConsumerMode

options = ConsumerOptions(
    batch_size=10,
    batch_timeout_ms=5000,
)

consumer = EventConsumer(options=options)

@consumer.on("log.record")
def process_logs(event):
    # 批量处理日志
    pass

consumer.start(mode=ConsumerMode.BATCH)
```

### 异步消费

```python
# 非阻塞模式启动
subscriber.start(blocking=False)

# 主程序继续执行其他任务
# ...

# 停止时
subscriber.stop()
```

## 架构图

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Order Service  │────▶│   Exchange   │◀────│ Inventory Svc   │
│   (Publisher)   │     │   (events)   │     │  (Subscriber)   │
└─────────────────┘     └──────┬───────┘     └─────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ Queue A  │    │ Queue B  │    │ Queue C  │
        │ (user.*) │    │ (order.#)│    │(payment) │
        └────┬─────┘    └────┬─────┘    └────┬─────┘
             │               │               │
             ▼               ▼               ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │Consumer 1│    │Consumer 2│    │Consumer 3│
        └──────────┘    └──────────┘    └──────────┘
```

## License

MIT
