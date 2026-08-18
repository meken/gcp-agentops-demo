"""Tools for Cymbal Retail Support Agent."""

import datetime
from typing import Dict, Any, Optional

# Mock database of customer orders
ORDERS_DB: Dict[str, Dict[str, Any]] = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "customer_id": "CUST-501",
        "customer_name": "Alice Johnson",
        "status": "DELIVERED",
        "order_date": "2026-08-01",
        "delivery_date": "2026-08-05",
        "items": [
            {"sku": "SKU-HEADPHONES-01", "name": "Wireless Noise Cancelling Headphones", "qty": 1, "price": 199.99}
        ],
        "total_amount": 199.99,
        "refund_status": "NONE",
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "customer_id": "CUST-502",
        "customer_name": "Bob Smith",
        "status": "IN_TRANSIT",
        "order_date": "2026-08-15",
        "estimated_delivery": "2026-08-20",
        "items": [
            {"sku": "SKU-KEYBOARD-02", "name": "Ergonomic Mechanical Keyboard", "qty": 1, "price": 129.50},
            {"sku": "SKU-MOUSE-03", "name": "Precision Wireless Mouse", "qty": 1, "price": 49.99}
        ],
        "total_amount": 179.49,
        "refund_status": "NONE",
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "customer_id": "CUST-503",
        "customer_name": "Carol Danvers",
        "status": "DELIVERED",
        "order_date": "2026-07-10",
        "delivery_date": "2026-07-14",
        "items": [
            {"sku": "SKU-SMARTWATCH-04", "name": "Ultra Fitness Smartwatch", "qty": 1, "price": 249.00}
        ],
        "total_amount": 249.00,
        "refund_status": "REFUNDED",
    },
}

# Mock database of product inventory
INVENTORY_DB: Dict[str, Dict[str, Any]] = {
    "SKU-HEADPHONES-01": {"name": "Wireless Noise Cancelling Headphones", "stock": 42, "warehouse": "us-central1-a", "price": 199.99},
    "SKU-KEYBOARD-02": {"name": "Ergonomic Mechanical Keyboard", "stock": 15, "warehouse": "us-east1-b", "price": 129.50},
    "SKU-MOUSE-03": {"name": "Precision Wireless Mouse", "stock": 88, "warehouse": "us-central1-a", "price": 49.99},
    "SKU-SMARTWATCH-04": {"name": "Ultra Fitness Smartwatch", "stock": 0, "warehouse": "us-west1-a", "price": 249.00},
}

# Knowledge base / FAQ entries
FAQ_DB: Dict[str, str] = {
    "return_policy": "Cymbal Retail offers a 30-day money-back guarantee on all delivered items. Items must be in original condition.",
    "shipping_policy": "Standard shipping takes 3-5 business days. Express shipping takes 1-2 business days.",
    "warranty": "All electronics include a standard 1-year limited manufacturer warranty covering defects in materials and workmanship.",
    "international_shipping": "We currently ship to the US, Canada, EU, and UK.",
}


def lookup_order(order_id: str) -> Dict[str, Any]:
    """Looks up customer order details by order ID.

    Args:
        order_id: The unique order identifier (e.g. 'ORD-1001').

    Returns:
        A dictionary containing the order details, status, items, and total amount.
    """
    order = ORDERS_DB.get(order_id.strip().upper())
    if not order:
        return {"error": f"Order with ID '{order_id}' was not found in the database."}
    return {"status": "SUCCESS", "order": order}


def check_inventory(sku_or_name: str) -> Dict[str, Any]:
    """Checks the stock availability and warehouse location for a product.

    Args:
        sku_or_name: Product SKU (e.g. 'SKU-HEADPHONES-01') or common product name keyword.

    Returns:
        A dictionary containing stock level, price, and warehouse location.
    """
    query = sku_or_name.strip().upper()
    if query in INVENTORY_DB:
        return {"status": "SUCCESS", "product": INVENTORY_DB[query]}

    # Partial search by name
    matches = [item for item in INVENTORY_DB.values() if sku_or_name.lower() in item["name"].lower()]
    if matches:
        return {"status": "SUCCESS", "matches": matches}

    return {"error": f"No product found matching '{sku_or_name}'."}


def process_refund(order_id: str, reason: str, amount: float) -> Dict[str, Any]:
    """Processes a return and refund for a delivered customer order.

    Args:
        order_id: The unique order identifier (e.g. 'ORD-1001').
        reason: The reason for requesting a refund.
        amount: The refund amount requested.

    Returns:
        A dictionary with refund confirmation details, transaction ID, and status.
    """
    order_key = order_id.strip().upper()
    order = ORDERS_DB.get(order_key)
    if not order:
        return {"error": f"Cannot process refund: Order '{order_id}' not found."}

    if order["status"] != "DELIVERED":
        return {"error": f"Cannot process refund: Order '{order_id}' status is '{order['status']}'. Only DELIVERED orders are eligible for refund."}

    if order["refund_status"] == "REFUNDED":
        return {"error": f"Cannot process refund: Order '{order_id}' has already been refunded."}

    if amount <= 0 or amount > order["total_amount"]:
        return {"error": f"Invalid refund amount ${amount:.2f}. Must be between $0.01 and the order total ${order['total_amount']:.2f}."}

    # Process refund
    order["refund_status"] = "REFUNDED"
    tx_id = f"REF-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}"

    return {
        "status": "APPROVED",
        "transaction_id": tx_id,
        "order_id": order_key,
        "refund_amount": amount,
        "reason": reason,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "message": f"Refund of ${amount:.2f} successfully issued for {order_key}."
    }


def search_product_faq(topic: str) -> Dict[str, Any]:
    """Searches Cymbal Retail store policies and frequently asked questions.

    Args:
        topic: The topic to look up (e.g. 'return_policy', 'warranty', 'shipping_policy').

    Returns:
        A dictionary containing the policy statement and relevant details.
    """
    topic_clean = topic.strip().lower().replace(" ", "_")
    for key, text in FAQ_DB.items():
        if key in topic_clean or topic_clean in key:
            return {"topic": key, "details": text}

    return {
        "topic": topic,
        "available_topics": list(FAQ_DB.keys()),
        "details": "General policy: Please contact support@cymbalretail.example.com for specialized inquiries."
    }
