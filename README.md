# Event Bus Framework

A lightweight, RESTful event subscription and publishing framework for distributed services.

## Features

- **RESTful API**: Simple HTTP-based event communication
- **Multiple Event Types**: Broadcast, Direct, and Topic-based messaging
- **Auto-discovery**: Services automatically register and heartbeat
- **Reliable Delivery**: Built-in retry mechanism with configurable policies
- **Priority Support**: Event priority levels (Low, Normal, High, Critical)
- **Easy Integration**: Simple client SDK for Python services

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Service A │     │  Event Bus  │     │   Service B │
│  (Publisher)│────▶│   Server    │◀────│ (Subscriber)│
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌─────────┐   ┌─────────┐
              │  Queue  │   │  Topic  │
              └─────────┘   └─────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Event Bus Server

```bash
python run_server.py --port 8000
```

The server will be available at:
- API: http://localhost:8000
- Health: http://localhost:8000/health
- Docs: http://localhost:8000/docs

### 3. Create a Service

```python
from event_bus import EventBusClient, Event, EventType

# Create client
client = EventBusClient(
    service_name="my-service",
    service_url="http://localhost:8001",
    event_bus_url="http://localhost:8000",
    topics=["user.created", "order.completed"]
)

# Define event handler
@client.handler.on_topic("user.created")
async def handle_user_created(event: Event):
    print(f"New user: {event.payload}")

# Start service
await client.start(host="0.0.0.0", port=8001)
```

### 4. Publish Events

```python
# Publish to a topic
await client.publish_topic(
    topic="user.created",
    payload={"user_id": "123", "name": "John"}
)

# Send direct message
await client.send_direct(
    target="notification-service",
    payload={"message": "Hello!"}
)

# Broadcast to all
await client.publish(
    payload={"announcement": "System update"},
    event_type=EventType.BROADCAST
)
```

## API Reference

### Subscribe

```http
POST /api/v1/subscribe
Content-Type: application/json

{
  "service_name": "my-service",
  "service_url": "http://localhost:8001/webhook",
  "event_types": ["broadcast", "topic"],
  "topics": ["user.created"],
  "retry_policy": {
    "max_retries": 3,
    "retry_interval": 5,
    "timeout": 30
  }
}
```

### Publish

```http
POST /api/v1/publish
Content-Type: application/json

{
  "event_type": "topic",
  "topic": "user.created",
  "target": null,
  "payload": {"user_id": "123"},
  "priority": 2,
  "metadata": {}
}
```

### Unsubscribe

```http
POST /api/v1/unsubscribe
Content-Type: application/json

{
  "service_name": "my-service",
  "subscription_id": "uuid"
}
```

### Heartbeat

```http
POST /api/v1/heartbeat
Content-Type: application/json

{
  "service_name": "my-service",
  "subscription_id": "uuid"
}
```

## Running Examples

### Demo with Multiple Services

```bash
# Terminal 1: Start Event Bus Server
python run_server.py --port 8000

# Terminal 2: Start Payment Service
python -m examples.payment_service

# Terminal 3: Start Inventory Service
python -m examples.inventory_service

# Terminal 4: Start Order Service
python -m examples.order_service
```

Or use the demo script (opens terminals automatically):

```bash
python run_demo.py
```

## Event Types

| Type | Description | Use Case |
|------|-------------|----------|
| `broadcast` | Sent to all subscribers | System announcements |
| `direct` | Sent to specific service | Service-to-service calls |
| `topic` | Sent to topic subscribers | Pub/Sub messaging |

## Testing

Run API tests:

```bash
# Start the server first
python run_server.py &

# Run tests
python test_api.py
```

## Configuration

Environment variables:

```bash
# Server
EVENT_BUS_HOST=0.0.0.0
EVENT_BUS_PORT=8000
EVENT_BUS_LOG_LEVEL=INFO

# Client
EVENT_CLIENT_SERVICE_NAME=my-service
EVENT_CLIENT_SERVICE_URL=http://localhost:8001
EVENT_CLIENT_EVENT_BUS_URL=http://localhost:8000
```

## Project Structure

```
event_bus_frame/
├── event_bus/           # Core framework
│   ├── __init__.py
│   ├── models.py        # Data models
│   ├── client.py        # Client SDK
│   ├── server.py        # Server implementation
│   └── exceptions.py    # Custom exceptions
├── examples/            # Example services
│   ├── order_service.py
│   ├── payment_service.py
│   └── inventory_service.py
├── run_server.py        # Server launcher
├── run_demo.py          # Demo script
├── test_api.py          # API tests
├── config.py            # Configuration
└── requirements.txt
```

## License

MIT
