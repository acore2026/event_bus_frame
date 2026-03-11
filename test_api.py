#!/usr/bin/env python3
"""
API Test Script for Event Bus Framework

Tests all endpoints of the Event Bus Server.
"""

import asyncio
import json
import sys
import httpx
from typing import Optional


class EventBusAPITester:
    """Test client for Event Bus API"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=10.0)
        self.subscription_id: Optional[str] = None

    async def test_health(self):
        """Test health endpoint"""
        print("\n[TEST] Health Check")
        print("-" * 40)

        response = await self.client.get(f"{self.base_url}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        assert response.status_code == 200, "Health check failed"
        print("✓ Health check passed")
        return True

    async def test_subscribe(self):
        """Test subscription endpoint"""
        print("\n[TEST] Subscribe")
        print("-" * 40)

        payload = {
            "service_name": "test-service",
            "service_url": "http://localhost:9000/webhook",
            "event_types": ["broadcast", "topic"],
            "topics": ["test.topic", "user.created"]
        }

        response = await self.client.post(
            f"{self.base_url}/api/v1/subscribe",
            json=payload
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")

        assert response.status_code == 200, "Subscription failed"
        assert data.get("success") is True, "Subscription not successful"

        self.subscription_id = data.get("subscription_id")
        print(f"✓ Subscribed with ID: {self.subscription_id}")
        return True

    async def test_list_subscriptions(self):
        """Test list subscriptions endpoint"""
        print("\n[TEST] List Subscriptions")
        print("-" * 40)

        response = await self.client.get(f"{self.base_url}/api/v1/subscriptions")
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Count: {data.get('count')}")
        print(f"Subscriptions: {json.dumps(data.get('subscriptions', []), indent=2)}")

        assert response.status_code == 200, "List subscriptions failed"
        print("✓ List subscriptions passed")
        return True

    async def test_heartbeat(self):
        """Test heartbeat endpoint"""
        print("\n[TEST] Heartbeat")
        print("-" * 40)

        if not self.subscription_id:
            print("⚠ No subscription ID, skipping heartbeat test")
            return True

        payload = {
            "service_name": "test-service",
            "subscription_id": self.subscription_id
        }

        response = await self.client.post(
            f"{self.base_url}/api/v1/heartbeat",
            json=payload
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 200, "Heartbeat failed"
        print("✓ Heartbeat passed")
        return True

    async def test_publish_broadcast(self):
        """Test publishing broadcast event"""
        print("\n[TEST] Publish Broadcast Event")
        print("-" * 40)

        payload = {
            "event_type": "broadcast",
            "payload": {
                "message": "Hello, world!",
                "timestamp": "2024-01-01T00:00:00Z"
            },
            "priority": 2
        }

        response = await self.client.post(
            f"{self.base_url}/api/v1/publish",
            json=payload
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")

        assert response.status_code == 200, "Publish failed"
        assert data.get("success") is True, "Publish not successful"
        print("✓ Publish broadcast passed")
        return True

    async def test_publish_topic(self):
        """Test publishing topic event"""
        print("\n[TEST] Publish Topic Event")
        print("-" * 40)

        payload = {
            "event_type": "topic",
            "topic": "test.topic",
            "payload": {
                "user_id": "12345",
                "action": "signup"
            },
            "priority": 3
        }

        response = await self.client.post(
            f"{self.base_url}/api/v1/publish",
            json=payload
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")

        assert response.status_code == 200, "Publish failed"
        print("✓ Publish topic passed")
        return True

    async def test_publish_direct(self):
        """Test publishing direct event"""
        print("\n[TEST] Publish Direct Event")
        print("-" * 40)

        payload = {
            "event_type": "direct",
            "target": "test-service",
            "payload": {
                "command": "execute",
                "params": {"key": "value"}
            }
        }

        response = await self.client.post(
            f"{self.base_url}/api/v1/publish",
            json=payload
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")

        assert response.status_code == 200, "Publish failed"
        print("✓ Publish direct passed")
        return True

    async def test_stats(self):
        """Test stats endpoint"""
        print("\n[TEST] Stats")
        print("-" * 40)

        response = await self.client.get(f"{self.base_url}/api/v1/stats")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        assert response.status_code == 200, "Stats failed"
        print("✓ Stats passed")
        return True

    async def test_unsubscribe(self):
        """Test unsubscribe endpoint"""
        print("\n[TEST] Unsubscribe")
        print("-" * 40)

        if not self.subscription_id:
            print("⚠ No subscription ID, skipping unsubscribe test")
            return True

        payload = {
            "service_name": "test-service",
            "subscription_id": self.subscription_id
        }

        response = await self.client.post(
            f"{self.base_url}/api/v1/unsubscribe",
            json=payload
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 200, "Unsubscribe failed"
        print("✓ Unsubscribe passed")
        return True

    async def run_all_tests(self):
        """Run all tests"""
        print("=" * 60)
        print("Event Bus API Tests")
        print("=" * 60)
        print(f"Base URL: {self.base_url}")

        tests = [
            ("Health", self.test_health),
            ("Subscribe", self.test_subscribe),
            ("List Subscriptions", self.test_list_subscriptions),
            ("Heartbeat", self.test_heartbeat),
            ("Publish Broadcast", self.test_publish_broadcast),
            ("Publish Topic", self.test_publish_topic),
            ("Publish Direct", self.test_publish_direct),
            ("Stats", self.test_stats),
            ("Unsubscribe", self.test_unsubscribe),
        ]

        results = []
        for name, test_func in tests:
            try:
                await test_func()
                results.append((name, True, None))
            except AssertionError as e:
                results.append((name, False, str(e)))
            except Exception as e:
                results.append((name, False, f"{type(e).__name__}: {e}"))

        # Summary
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)

        passed = sum(1 for _, result, _ in results if result)
        failed = len(results) - passed

        for name, result, error in results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{status}: {name}")
            if error:
                print(f"  Error: {error}")

        print("-" * 60)
        print(f"Total: {len(results)}, Passed: {passed}, Failed: {failed}")

        await self.client.aclose()
        return failed == 0


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Event Bus API Tester")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Event Bus Server URL (default: http://localhost:8000)"
    )

    args = parser.parse_args()

    tester = EventBusAPITester(args.url)
    success = await tester.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
