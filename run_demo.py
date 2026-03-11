#!/usr/bin/env python3
"""
Demo script to run all services

This script starts:
1. Event Bus Server
2. Order Service
3. Payment Service
4. Inventory Service

Then creates sample orders to demonstrate the event flow.
"""

import asyncio
import subprocess
import sys
import time
import signal
import os


def run_in_terminal(title, command, delay=0):
    """Run a command in a new terminal window"""
    time.sleep(delay)

    # Detect desktop environment
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

    if "gnome" in desktop or "ubuntu" in desktop:
        cmd = ["gnome-terminal", "--title", title, "--", "bash", "-c", f"{command}; exec bash"]
    elif "kde" in desktop:
        cmd = ["konsole", "--title", title, "-e", "bash", "-c", f"{command}; exec bash"]
    elif "xfce" in desktop:
        cmd = ["xfce4-terminal", "--title", title, "-e", f"bash -c '{command}; exec bash'"]
    else:
        # Fallback - run in background
        print(f"[{title}] {command}")
        return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        return subprocess.Popen(cmd)
    except FileNotFoundError:
        # Terminal emulator not found, run in background
        print(f"[{title}] {command}")
        return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


async def main():
    """Run the demo"""
    print("=" * 70)
    print("Event Bus Framework Demo")
    print("=" * 70)
    print()
    print("This demo will start:")
    print("  1. Event Bus Server (port 8000)")
    print("  2. Order Service (port 8001)")
    print("  3. Payment Service (port 8002)")
    print("  4. Inventory Service (port 8003)")
    print()
    print("Press Ctrl+C to stop all services")
    print("=" * 70)
    print()

    processes = []

    try:
        # Start Event Bus Server
        print("[1/4] Starting Event Bus Server...")
        p1 = run_in_terminal(
            "Event Bus Server",
            f"{sys.executable} run_server.py --port 8000",
            delay=0.5
        )
        processes.append(p1)

        # Wait for server to start
        await asyncio.sleep(3)

        # Start Payment Service
        print("[2/4] Starting Payment Service...")
        p2 = run_in_terminal(
            "Payment Service",
            f"{sys.executable} -m examples.payment_service",
            delay=0.5
        )
        processes.append(p2)

        # Start Inventory Service
        print("[3/4] Starting Inventory Service...")
        p3 = run_in_terminal(
            "Inventory Service",
            f"{sys.executable} -m examples.inventory_service",
            delay=0.5
        )
        processes.append(p3)

        # Start Order Service
        print("[4/4] Starting Order Service...")
        p4 = run_in_terminal(
            "Order Service",
            f"{sys.executable} -m examples.order_service",
            delay=0.5
        )
        processes.append(p4)

        print()
        print("All services started!")
        print("- Event Bus: http://localhost:8000")
        print("- Order Service: http://localhost:8001")
        print("- Payment Service: http://localhost:8002")
        print("- Inventory Service: http://localhost:8003")
        print()
        print("Press Ctrl+C to stop all services")

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n\nStopping all services...")
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=2)
            except:
                p.kill()
        print("All services stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
