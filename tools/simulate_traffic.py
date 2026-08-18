#!/usr/bin/env python3
"""Simulate realistic production traffic against the deployed Agent Runtime agent.

Used in Challenge 5 to generate production traces for Online Evaluation.
"""

import argparse
import asyncio
import random
import sys

import vertexai

TRAFFIC_SCENARIOS = [
    {
        "name": "Order Status Inquiry",
        "turns": [
            "Hi, can you check the status of my order ORD-1001?",
            "When was it delivered and what items were in it?",
        ],
    },
    {
        "name": "In-Transit Order Inquiry",
        "turns": [
            "Where is my package for order ORD-1002?",
            "What is the estimated delivery date?",
        ],
    },
    {
        "name": "Inventory & Stock Check",
        "turns": [
            "Do you have the Wireless Noise Cancelling Headphones in stock?",
            "How many units are available and what is the price?",
        ],
    },
    {
        "name": "Stock Availability & Alternative",
        "turns": [
            "Is the Ultra Fitness Smartwatch in stock right now?",
            "What about mechanical keyboards?",
        ],
    },
    {
        "name": "Store Policy & Return Window",
        "turns": [
            "What is your return policy for electronics?",
            "Does my purchase come with a warranty?",
        ],
    },
    {
        "name": "Valid Refund Request",
        "turns": [
            "I would like to return order ORD-1001 because the headphones didn't fit comfortably.",
            "Yes, please process a full refund of $199.99 for ORD-1001.",
        ],
    },
    {
        "name": "Invalid Refund (In-Transit Item)",
        "turns": [
            "I want a refund for order ORD-1002.",
            "Can you cancel and refund it right now?",
        ],
    },
    {
        "name": "Already Refunded Order Check",
        "turns": [
            "Can you check if order ORD-1003 has been refunded yet?",
        ],
    },
]


async def run_traffic_simulation(
    resource_name: str, location: str, total_sessions: int, delay_seconds: float
):
    print("============================================================")
    print("Starting Production Traffic Simulation for Online Evaluation")
    print(f"Target: {resource_name}")
    print(f"Location: {location}")
    print(f"Total Sessions to Simulate: {total_sessions}")
    print("============================================================\n")

    client = vertexai.Client(location=location)
    agent = client.agent_engines.get(name=resource_name)

    for session_idx in range(1, total_sessions + 1):
        scenario = random.choice(TRAFFIC_SCENARIOS)
        user_id = f"sim-user-{random.randint(1000, 9999)}"
        print(
            f"[{session_idx}/{total_sessions}] Starting Scenario: '{scenario['name']}' (User: {user_id})"
        )

        for turn_idx, user_message in enumerate(scenario["turns"], 1):
            print(f"  [Turn {turn_idx}] User: {user_message}")
            try:
                response_text = ""
                async for event in agent.async_stream_query(
                    message=user_message, user_id=user_id
                ):
                    if hasattr(event, "text") and event.text:
                        response_text += event.text
                    elif isinstance(event, dict) and "text" in event:
                        response_text += event["text"]
                print(f"  [Turn {turn_idx}] Agent: {response_text.strip()[:120]}...\n")
            except Exception as e:
                print(f"  [Turn {turn_idx}] Error during query: {e}\n", file=sys.stderr)

            await asyncio.sleep(1.0)

        print(
            f"Completed scenario '{scenario['name']}'. Pausing {delay_seconds}s before next session...\n"
        )
        await asyncio.sleep(delay_seconds)

    print("============================================================")
    print(
        "Traffic Simulation Completed! Production traces are captured in Cloud Trace."
    )
    print(
        "Check the Agent Platform Online Evaluation dashboard for live quality scores."
    )
    print("============================================================")


def main():
    parser = argparse.ArgumentParser(
        description="Simulate production traffic for Agent Runtime"
    )
    parser.add_argument(
        "--resource-name",
        required=True,
        help="Agent Runtime Reasoning Engine resource name",
    )
    parser.add_argument("--location", default="us-central1", help="Google Cloud region")
    parser.add_argument(
        "--sessions",
        type=int,
        default=10,
        help="Number of simulated conversation sessions",
    )
    parser.add_argument(
        "--delay", type=float, default=2.0, help="Delay between sessions in seconds"
    )

    args = parser.parse_args()
    asyncio.run(
        run_traffic_simulation(
            args.resource_name, args.location, args.sessions, args.delay
        )
    )


if __name__ == "__main__":
    main()
