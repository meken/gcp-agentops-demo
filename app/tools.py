import datetime
from typing import Any

from . import database


def lookup_order(order_id: str) -> dict[str, Any]:
    """Looks up customer order details by order ID from Firestore.

    Args:
        order_id: The unique order identifier (e.g. 'ORD-1001').

    Returns:
        A dictionary containing the order details, status, items, and total amount.
    """
    clean_id = order_id.strip().upper()
    try:
        doc = database.get_orders_collection().document(clean_id).get()
        if not doc.exists:
            return {
                "error": f"Order with ID '{order_id}' was not found in the database."
            }
        return {"status": "SUCCESS", "order": doc.to_dict()}
    except Exception as e:
        return {"error": f"Database error looking up order '{order_id}': {e!s}"}


def check_inventory(sku_or_name: str) -> dict[str, Any]:
    """Checks the stock availability and warehouse location for a product from Firestore.

    Args:
        sku_or_name: Product SKU (e.g. 'SKU-HEADPHONES-01') or common product name keyword.

    Returns:
        A dictionary containing stock level, price, and warehouse location.
    """
    clean_query = sku_or_name.strip()
    try:
        # 1. Exact lookup by SKU
        sku_doc = (
            database.get_inventory_collection().document(clean_query.upper()).get()
        )
        if sku_doc.exists:
            return {"status": "SUCCESS", "product": sku_doc.to_dict()}

        # 2. Search by product name keyword across inventory
        matches = []
        for doc in database.get_inventory_collection().stream():
            item = doc.to_dict()
            if item and clean_query.lower() in item.get("name", "").lower():
                matches.append(item)

        if matches:
            return {"status": "SUCCESS", "matches": matches}

        return {"error": f"No product found matching '{sku_or_name}'."}
    except Exception as e:
        return {
            "error": f"Database error checking inventory for '{sku_or_name}': {e!s}"
        }


def process_refund(order_id: str, reason: str, amount: float) -> dict[str, Any]:
    """Processes a return and refund for an eligible delivered customer order in Firestore.

    Args:
        order_id: The unique order identifier (e.g. 'ORD-1001').
        reason: The reason for requesting a refund.
        amount: The refund amount requested.

    Returns:
        A dictionary with refund confirmation details, transaction ID, and status.
    """
    clean_id = order_id.strip().upper()
    try:
        order_ref = database.get_orders_collection().document(clean_id)
        doc = order_ref.get()

        if not doc.exists:
            return {"error": f"Cannot process refund: Order '{order_id}' not found."}

        order = doc.to_dict() or {}

        if order.get("status") != "DELIVERED":
            return {
                "error": (
                    f"Cannot process refund: Order '{order_id}' status is '{order.get('status')}'. "
                    "Only DELIVERED orders are eligible for refund."
                )
            }

        if order.get("refund_status") == "REFUNDED":
            return {
                "error": f"Cannot process refund: Order '{order_id}' has already been refunded."
            }

        total_amount = float(order.get("total_amount", 0.0))
        if amount <= 0 or amount > total_amount:
            return {
                "error": (
                    f"Invalid refund amount ${amount:.2f}. "
                    f"Must be between $0.01 and the order total ${total_amount:.2f}."
                )
            }

        # Validate 30-day return window if delivery_date or order_date is present
        delivery_date_str = order.get("delivery_date") or order.get("order_date")
        if delivery_date_str:
            try:
                delivery_date = datetime.date.fromisoformat(delivery_date_str)
                days_since_delivery = (datetime.date.today() - delivery_date).days
                if days_since_delivery > 30:
                    return {
                        "error": (
                            f"Cannot process refund: Order '{order_id}' was delivered on {delivery_date_str} "
                            f"({days_since_delivery} days ago). Refunds are only permitted within 30 days."
                        )
                    }
            except (ValueError, TypeError):
                pass  # Fall back to allowing if date parsing is unparseable

        now_utc = datetime.datetime.now(datetime.UTC)
        tx_id = f"REF-{now_utc.strftime('%Y%m%d%H%M%S')}"

        # Atomically update order and record transaction
        db = database.get_db()
        batch = db.batch()
        batch.update(order_ref, {"refund_status": "REFUNDED", "last_refund_tx": tx_id})

        refund_record_ref = database.get_refunds_collection().document(tx_id)
        batch.set(
            refund_record_ref,
            {
                "transaction_id": tx_id,
                "order_id": clean_id,
                "refund_amount": amount,
                "reason": reason,
                "timestamp": now_utc.isoformat(),
                "status": "APPROVED",
            },
        )
        batch.commit()

        return {
            "status": "APPROVED",
            "transaction_id": tx_id,
            "order_id": clean_id,
            "refund_amount": amount,
            "reason": reason,
            "timestamp": now_utc.isoformat(),
            "message": f"Refund of ${amount:.2f} successfully issued for {clean_id}.",
        }
    except Exception as e:
        return {"error": f"Database error processing refund for '{order_id}': {e!s}"}


def search_product_faq(topic: str) -> dict[str, Any]:
    """Searches Cymbal Retail store policies and frequently asked questions from Firestore.

    Args:
        topic: The topic to look up (e.g. 'return_policy', 'warranty', 'shipping_policy').

    Returns:
        A dictionary containing the policy statement and relevant details.
    """
    topic_clean = topic.strip().lower().replace(" ", "_")
    try:
        # 1. Exact topic document lookup
        doc = database.get_faqs_collection().document(topic_clean).get()
        if doc.exists:
            data = doc.to_dict() or {}
            return {
                "topic": data.get("topic", topic_clean),
                "details": data.get("details", ""),
            }

        # 2. Substring matching across all FAQ documents
        all_topics = []
        for faq_doc in database.get_faqs_collection().stream():
            data = faq_doc.to_dict() or {}
            key = data.get("topic", faq_doc.id)
            all_topics.append(key)
            if key in topic_clean or topic_clean in key:
                return {"topic": key, "details": data.get("details", "")}

        return {
            "topic": topic,
            "available_topics": all_topics,
            "details": (
                "General policy: Please contact support@cymbalretail.example.com for specialized inquiries."
            ),
        }
    except Exception as e:
        return {"error": f"Database error searching FAQ for '{topic}': {e!s}"}
