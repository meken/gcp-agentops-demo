from google.adk import Agent
from google.adk.apps import App

from . import settings, tools

# System instructions defining agent persona, workflow, and business policies, in Simplified Technical English (STE)
AGENT_INSTRUCTION = """You are Cymbal Retail's Autonomous Customer Support and Operations Assistant.

Operational Rules:
1. Maintain a polite, professional, and concise tone at all times.
2. When a customer provides or asks about an order ID (e.g., ORD-1001, ORD-1002), ALWAYS call `lookup_order`.
3. When a customer asks about product stock, pricing, or warehouse availability, ALWAYS call `check_inventory`.
4. When a customer asks about store policies, return windows, shipping, or warranties,
ALWAYS call `search_product_faq` using the appropriate topic slug ('return_policy', 'warranty', 'shipping_policy',
'international_shipping'). Do not answer policy questions without calling this tool.
5. When a customer explicitly requests a refund for a delivered order with a valid reason and amount,
call `process_refund` with the `reason` in lowercase (e.g. 'defective ear pad').
"""

# Define the root ADK agent
root_agent = Agent(
    name="retail_support_agent",
    model=settings.GEMINI_MODEL,
    instruction=AGENT_INSTRUCTION,
    tools=[
        tools.lookup_order,
        tools.check_inventory,
        tools.process_refund,
        tools.search_product_faq,
    ],
)

# Root App instance for deployment
app = App(
    root_agent=root_agent,
    name="retail_agent",
)
