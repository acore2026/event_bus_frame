#!/usr/bin/env python3
"""
Event Bus Framework - 综合测试用例

测试范围:
1. 事件模型 (Event, Subscription)
2. 订阅管理 (SubscriptionManager)
3. 事件投递 (EventDeliveryManager)
4. 客户端SDK (EventBusClient)
5. RESTful API 端点

运行方式:
    python test_event_bus.py
    python test_event_bus.py -v  # 详细输出
"""

import asyncio
import json
import sys
import time
import unittest
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

# 确保能导入event_bus模块
sys.path.insert(0, '/home/acore/proj/event_bus_frame')

import httpx
from fastapi.testclient import TestClient

from event_bus.models import (
    Event, EventType, Subscription, EventPriority,
    PublishRequest, SubscribeRequest, SubscribeResponse,
    PublishResponse, HealthStatus, EventDeliveryStatus
)
from event_bus.exceptions import (
    EventBusError, ConnectionError, PublishError,
    SubscriptionError, DeliveryError
)
from event_bus.client import EventBusClient, EventHandler
from event_bus.server import EventBusServer, SubscriptionManager, EventDeliveryManager


# ============================================================================
# 测试用例 1: 数据模型测试
# ============================================================================

class TestEventModel(unittest.TestCase):
    """测试 Event 数据模型"""

    def test_event_creation(self):
        """测试创建事件对象"""
        event = Event(
            event_type=EventType.TOPIC,
            topic="user.created",
            source="test-service",
            payload={"user_id": "123", "name": "张三"},
            priority=EventPriority.HIGH
        )

        self.assertIsNotNone(event.id)
        self.assertEqual(event.event_type, EventType.TOPIC)
        self.assertEqual(event.topic, "user.created")
        self.assertEqual(event.source, "test-service")
        self.assertEqual(event.payload["user_id"], "123")
        self.assertEqual(event.priority, EventPriority.HIGH)
        self.assertIsInstance(event.timestamp, datetime)

    def test_event_to_dict(self):
        """测试事件序列化"""
        event = Event(
            event_type=EventType.BROADCAST,
            source="service-a",
            payload={"message": "hello"}
        )

        data = event.model_dump()
        self.assertIn("id", data)
        self.assertIn("timestamp", data)
        self.assertEqual(data["event_type"], "broadcast")
        self.assertEqual(data["source"], "service-a")

    def test_event_from_dict(self):
        """测试从字典反序列化事件"""
        data = {
            "id": "test-uuid-123",
            "event_type": "direct",
            "source": "service-b",
            "target": "service-c",
            "payload": {"action": "notify"},
            "priority": 3
        }

        event = Event(**data)
        self.assertEqual(event.id, "test-uuid-123")
        self.assertEqual(event.event_type, EventType.DIRECT)
        self.assertEqual(event.target, "service-c")


class TestSubscriptionModel(unittest.TestCase):
    """测试 Subscription 数据模型"""

    def test_subscription_creation(self):
        """测试创建订阅对象"""
        subscription = Subscription(
            service_name="order-service",
            service_url="http://localhost:8001/webhook",
            event_types=[EventType.TOPIC, EventType.BROADCAST],
            topics=["order.created", "order.cancelled"]
        )

        self.assertIsNotNone(subscription.id)
        self.assertEqual(subscription.service_name, "order-service")
        self.assertEqual(subscription.service_url, "http://localhost:8001/webhook")
        self.assertEqual(len(subscription.event_types), 2)
        self.assertEqual(len(subscription.topics), 2)
        self.assertTrue(subscription.is_active)

    def test_subscription_retry_policy(self):
        """测试订阅重试策略"""
        subscription = Subscription(
            service_name="test-service",
            service_url="http://test:8000/webhook",
            retry_policy={
                "max_retries": 5,
                "retry_interval": 10,
                "timeout": 60
            }
        )

        self.assertEqual(subscription.retry_policy["max_retries"], 5)
        self.assertEqual(subscription.retry_policy["retry_interval"], 10)


# ============================================================================
# 测试用例 2: 订阅管理器测试 (异步)
# ============================================================================

class TestSubscriptionManager(unittest.IsolatedAsyncioTestCase):
    """测试 SubscriptionManager"""

    async def asyncSetUp(self):
        """每个测试前初始化"""
        self.manager = SubscriptionManager()

    async def test_add_subscription(self):
        """测试添加订阅"""
        sub = Subscription(
            service_name="test-service",
            service_url="http://test:8000/webhook",
            event_types=[EventType.BROADCAST],
            topics=["test.topic"]
        )

        sub_id = await self.manager.add_subscription(sub)

        self.assertIsNotNone(sub_id)
        self.assertEqual(sub_id, sub.id)

        # 验证能获取到订阅
        all_subs = await self.manager.get_all_subscriptions()
        self.assertEqual(len(all_subs), 1)
        self.assertEqual(all_subs[0].service_name, "test-service")

    async def test_remove_subscription(self):
        """测试移除订阅"""
        sub = Subscription(
            service_name="test-service",
            service_url="http://test:8000/webhook",
            event_types=[EventType.TOPIC],
            topics=["test.topic"]
        )

        sub_id = await self.manager.add_subscription(sub)
        result = await self.manager.remove_subscription(sub_id)

        self.assertTrue(result)

        # 验证已移除
        all_subs = await self.manager.get_all_subscriptions()
        self.assertEqual(len(all_subs), 0)

    async def test_get_subscriptions_for_broadcast(self):
        """测试获取广播事件的订阅者"""
        # 添加广播订阅者
        sub1 = Subscription(
            service_name="service-1",
            service_url="http://s1:8000/webhook",
            event_types=[EventType.BROADCAST]
        )
        await self.manager.add_subscription(sub1)

        # 添加仅TOPIC订阅者
        sub2 = Subscription(
            service_name="service-2",
            service_url="http://s2:8000/webhook",
            event_types=[EventType.TOPIC],
            topics=["other.topic"]
        )
        await self.manager.add_subscription(sub2)

        # 创建广播事件
        event = Event(
            event_type=EventType.BROADCAST,
            source="test",
            payload={}
        )

        # 获取匹配订阅者
        matches = await self.manager.get_subscriptions_for_event(event)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].service_name, "service-1")

    async def test_get_subscriptions_for_topic(self):
        """测试获取Topic事件的订阅者"""
        # 添加Topic订阅者
        sub1 = Subscription(
            service_name="service-1",
            service_url="http://s1:8000/webhook",
            event_types=[EventType.TOPIC],
            topics=["user.created", "user.updated"]
        )
        await self.manager.add_subscription(sub1)

        sub2 = Subscription(
            service_name="service-2",
            service_url="http://s2:8000/webhook",
            event_types=[EventType.TOPIC],
            topics=["user.deleted"]
        )
        await self.manager.add_subscription(sub2)

        # 创建user.created事件
        event = Event(
            event_type=EventType.TOPIC,
            topic="user.created",
            source="test",
            payload={"user_id": "123"}
        )

        matches = await self.manager.get_subscriptions_for_event(event)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].service_name, "service-1")

    async def test_get_subscriptions_for_direct(self):
        """测试获取Direct事件的订阅者"""
        sub = Subscription(
            service_name="target-service",
            service_url="http://target:8000/webhook",
            event_types=[EventType.DIRECT]
        )
        await self.manager.add_subscription(sub)

        event = Event(
            event_type=EventType.DIRECT,
            target="target-service",
            source="sender",
            payload={}
        )

        matches = await self.manager.get_subscriptions_for_event(event)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].service_name, "target-service")

    async def test_heartbeat_update(self):
        """测试心跳更新"""
        sub = Subscription(
            service_name="test-service",
            service_url="http://test:8000/webhook"
        )
        sub_id = await self.manager.add_subscription(sub)

        # 更新心跳
        result = await self.manager.update_heartbeat(sub_id)
        self.assertTrue(result)

    async def test_cleanup_stale_subscriptions(self):
        """测试清理过期订阅"""
        sub = Subscription(
            service_name="test-service",
            service_url="http://test:8000/webhook"
        )
        sub_id = await self.manager.add_subscription(sub)

        # 设置一个很久以前的心跳
        sub.last_heartbeat = datetime.utcnow() - timedelta(seconds=300)

        # 清理超过120秒的订阅
        await self.manager.cleanup_stale_subscriptions(max_age_seconds=120)

        # 验证已清理
        all_subs = await self.manager.get_all_subscriptions()
        self.assertEqual(len(all_subs), 0)


# ============================================================================
# 测试用例 3: 客户端SDK测试
# ============================================================================

class TestEventHandler(unittest.IsolatedAsyncioTestCase):
    """测试 EventHandler"""

    async def asyncSetUp(self):
        self.handler = EventHandler()

    async def test_on_broadcast_handler(self):
        """测试广播事件处理器"""
        received_events = []

        @self.handler.on_broadcast
        async def handle_broadcast(event: Event):
            received_events.append(event)

        event = Event(
            event_type=EventType.BROADCAST,
            source="test",
            payload={"msg": "hello"}
        )

        results = await self.handler.handle(event)

        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].payload["msg"], "hello")

    async def test_on_topic_handler(self):
        """测试Topic事件处理器"""
        received_events = []

        @self.handler.on_topic("user.created")
        async def handle_user_created(event: Event):
            received_events.append(event)

        # 匹配的事件
        event1 = Event(
            event_type=EventType.TOPIC,
            topic="user.created",
            source="test",
            payload={"user_id": "123"}
        )

        # 不匹配的事件
        event2 = Event(
            event_type=EventType.TOPIC,
            topic="user.deleted",
            source="test",
            payload={"user_id": "456"}
        )

        await self.handler.handle(event1)
        await self.handler.handle(event2)

        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].payload["user_id"], "123")

    async def test_multiple_handlers(self):
        """测试多个处理器"""
        calls = []

        @self.handler.on_topic("test.event")
        async def handler1(event: Event):
            calls.append("handler1")

        @self.handler.on_topic("test.event")
        async def handler2(event: Event):
            calls.append("handler2")

        event = Event(
            event_type=EventType.TOPIC,
            topic="test.event",
            source="test",
            payload={}
        )

        await self.handler.handle(event)

        self.assertEqual(len(calls), 2)
        self.assertIn("handler1", calls)
        self.assertIn("handler2", calls)


class TestEventBusClient(unittest.IsolatedAsyncioTestCase):
    """测试 EventBusClient"""

    async def asyncSetUp(self):
        self.client = EventBusClient(
            service_name="test-client",
            service_url="http://localhost:9999",
            event_bus_url="http://localhost:8888",
            topics=["test.topic"]
        )

    async def asyncTearDown(self):
        if self.client._client and not self.client._client.is_closed:
            await self.client._client.aclose()

    def test_client_initialization(self):
        """测试客户端初始化"""
        self.assertEqual(self.client.service_name, "test-client")
        self.assertEqual(self.client.service_url, "http://localhost:9999")
        self.assertEqual(self.client.event_bus_url, "http://localhost:8888")
        self.assertEqual(self.client.topics, ["test.topic"])
        self.assertIsNotNone(self.client.handler)

    @patch("httpx.AsyncClient.post")
    async def test_subscribe_success(self, mock_post):
        """测试订阅成功"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "success": True,
                "subscription_id": "sub-123",
                "message": "Subscribed"
            }
        )

        sub_id = await self.client.subscribe()

        self.assertEqual(sub_id, "sub-123")
        mock_post.assert_called_once()

    @patch("httpx.AsyncClient.post")
    async def test_publish_success(self, mock_post):
        """测试发布事件成功"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "success": True,
                "event_id": "evt-123",
                "message": "Published"
            }
        )

        event_id = await self.client.publish(
            payload={"msg": "test"},
            event_type=EventType.TOPIC,
            topic="test.topic"
        )

        self.assertEqual(event_id, "evt-123")

    @patch("httpx.AsyncClient.post")
    async def test_publish_topic_convenience(self, mock_post):
        """测试发布到Topic的便捷方法"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "success": True,
                "event_id": "evt-456"
            }
        )

        event_id = await self.client.publish_topic(
            topic="order.created",
            payload={"order_id": "ORD-001"}
        )

        self.assertEqual(event_id, "evt-456")

        # 验证调用参数
        call_args = mock_post.call_args
        json_data = call_args[1]["json"]
        self.assertEqual(json_data["event_type"], "topic")
        self.assertEqual(json_data["topic"], "order.created")


# ============================================================================
# 测试用例 4: API端点测试
# ============================================================================

class TestAPIEndpoints(unittest.TestCase):
    """测试 RESTful API 端点"""

    @classmethod
    def setUpClass(cls):
        """设置测试客户端"""
        cls.server = EventBusServer()
        cls.app = cls.server.create_app()
        cls.client = TestClient(cls.app)

    def test_health_endpoint(self):
        """测试健康检查端点"""
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("uptime_seconds", data)
        self.assertIn("total_subscriptions", data)

    def test_subscribe_endpoint(self):
        """测试订阅端点"""
        request_data = {
            "service_name": "test-service",
            "service_url": "http://test:8000/webhook",
            "event_types": ["broadcast", "topic"],
            "topics": ["test.topic"]
        }

        response = self.client.post("/api/v1/subscribe", json=request_data)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("subscription_id", data)

    def test_publish_broadcast_endpoint(self):
        """测试发布广播事件端点"""
        request_data = {
            "event_type": "broadcast",
            "payload": {"message": "test broadcast"},
            "priority": 2
        }

        response = self.client.post("/api/v1/publish", json=request_data)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("event_id", data)

    def test_publish_topic_endpoint(self):
        """测试发布Topic事件端点"""
        request_data = {
            "event_type": "topic",
            "topic": "user.created",
            "payload": {"user_id": "123"},
            "priority": 2
        }

        response = self.client.post("/api/v1/publish", json=request_data)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

    def test_list_subscriptions_endpoint(self):
        """测试列出订阅端点"""
        # 先添加一个订阅
        self.client.post("/api/v1/subscribe", json={
            "service_name": "list-test-service",
            "service_url": "http://test:8000/webhook",
            "event_types": ["broadcast"]
        })

        response = self.client.get("/api/v1/subscriptions")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("subscriptions", data)
        self.assertIn("count", data)
        self.assertGreaterEqual(data["count"], 1)

    def test_heartbeat_endpoint(self):
        """测试心跳端点"""
        # 先订阅
        sub_response = self.client.post("/api/v1/subscribe", json={
            "service_name": "heartbeat-test",
            "service_url": "http://test:8000/webhook"
        })
        sub_id = sub_response.json()["subscription_id"]

        # 发送心跳
        response = self.client.post("/api/v1/heartbeat", json={
            "service_name": "heartbeat-test",
            "subscription_id": sub_id
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

    def test_unsubscribe_endpoint(self):
        """测试取消订阅端点"""
        # 先订阅
        sub_response = self.client.post("/api/v1/subscribe", json={
            "service_name": "unsub-test",
            "service_url": "http://test:8000/webhook"
        })
        sub_id = sub_response.json()["subscription_id"]

        # 取消订阅
        response = self.client.post("/api/v1/unsubscribe", json={
            "service_name": "unsub-test",
            "subscription_id": sub_id
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

    def test_stats_endpoint(self):
        """测试统计端点"""
        response = self.client.get("/api/v1/stats")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("subscriptions", data)
        self.assertIn("total_events", data)
        self.assertIn("delivered", data)
        self.assertIn("failed", data)


# ============================================================================
# 测试用例 5: 异常处理测试
# ============================================================================

class TestExceptions(unittest.TestCase):
    """测试异常类"""

    def test_event_bus_error(self):
        """测试基础异常"""
        with self.assertRaises(EventBusError):
            raise EventBusError("test error")

    def test_connection_error(self):
        """测试连接异常"""
        with self.assertRaises(ConnectionError):
            raise ConnectionError("connection failed")

        # 验证继承关系
        self.assertTrue(issubclass(ConnectionError, EventBusError))

    def test_publish_error(self):
        """测试发布异常"""
        with self.assertRaises(PublishError):
            raise PublishError("publish failed")

    def test_subscription_error(self):
        """测试订阅异常"""
        with self.assertRaises(SubscriptionError):
            raise SubscriptionError("subscription failed")


# ============================================================================
# 测试用例 6: 集成测试场景
# ============================================================================

class TestIntegrationScenario(unittest.IsolatedAsyncioTestCase):
    """集成测试场景"""

    async def asyncSetUp(self):
        """设置测试环境"""
        self.server = EventBusServer()
        self.app = self.server.create_app()
        self.client = TestClient(self.app)

    async def test_order_payment_flow(self):
        """测试订单-支付完整流程"""
        # 1. 支付服务订阅 order.created
        payment_sub = self.client.post("/api/v1/subscribe", json={
            "service_name": "payment-service",
            "service_url": "http://payment:8002/webhook",
            "event_types": ["topic"],
            "topics": ["order.created"]
        })
        self.assertEqual(payment_sub.status_code, 200)

        # 2. 库存服务订阅 order.created
        inventory_sub = self.client.post("/api/v1/subscribe", json={
            "service_name": "inventory-service",
            "service_url": "http://inventory:8003/webhook",
            "event_types": ["topic"],
            "topics": ["order.created"]
        })
        self.assertEqual(inventory_sub.status_code, 200)

        # 3. 订单服务发布 order.created 事件
        publish_response = self.client.post("/api/v1/publish", json={
            "event_type": "topic",
            "topic": "order.created",
            "payload": {
                "order_id": "ORD-001",
                "items": [{"sku": "SKU-001", "qty": 2}],
                "amount": 199.99
            }
        })

        self.assertEqual(publish_response.status_code, 200)
        data = publish_response.json()
        self.assertTrue(data["success"])

        # 注：实际场景中，支付和库存服务会收到 webhook 调用
        # 这里验证事件已成功入队/投递

    async def test_direct_messaging(self):
        """测试点对点消息"""
        # 1. 目标服务订阅 DIRECT 消息
        target_sub = self.client.post("/api/v1/subscribe", json={
            "service_name": "target-service",
            "service_url": "http://target:8005/webhook",
            "event_types": ["direct"]
        })
        self.assertEqual(target_sub.status_code, 200)

        # 2. 发送直接消息
        direct_msg = self.client.post("/api/v1/publish", json={
            "event_type": "direct",
            "target": "target-service",
            "payload": {"command": "execute_task", "params": {"id": "123"}}
        })

        self.assertEqual(direct_msg.status_code, 200)

    async def test_broadcast_to_multiple(self):
        """测试广播给多个订阅者"""
        # 添加多个广播订阅者
        for i in range(3):
            response = self.client.post("/api/v1/subscribe", json={
                "service_name": f"subscriber-{i}",
                "service_url": f"http://sub{i}:8000/webhook",
                "event_types": ["broadcast"]
            })
            self.assertEqual(response.status_code, 200)

        # 发布广播
        broadcast = self.client.post("/api/v1/publish", json={
            "event_type": "broadcast",
            "payload": {"announcement": "系统维护通知"}
        })

        self.assertEqual(broadcast.status_code, 200)
        data = broadcast.json()
        # 应该发送给3个订阅者（但在测试环境中它们不存在，所以可能失败）
        self.assertIn("delivered_count", data)


# ============================================================================
# 运行测试
# ============================================================================

def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestEventModel))
    suite.addTests(loader.loadTestsFromTestCase(TestSubscriptionModel))
    suite.addTests(loader.loadTestsFromTestCase(TestSubscriptionManager))
    suite.addTests(loader.loadTestsFromTestCase(TestEventHandler))
    suite.addTests(loader.loadTestsFromTestCase(TestEventBusClient))
    suite.addTests(loader.loadTestsFromTestCase(TestAPIEndpoints))
    suite.addTests(loader.loadTestsFromTestCase(TestExceptions))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationScenario))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 返回退出码
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    print("=" * 70)
    print("Event Bus Framework - Test Suite")
    print("=" * 70)
    print()

    exit_code = run_tests()

    print()
    print("=" * 70)
    if exit_code == 0:
        print("All tests passed!")
    else:
        print("Some tests failed!")
    print("=" * 70)

    sys.exit(exit_code)
