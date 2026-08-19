import datetime
from unittest.mock import MagicMock, patch

import pytest

from app import tools

# Marking all tests in this file to be unit tests
pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Tests for lookup_order
# ---------------------------------------------------------------------------


def test_lookup_order_success():
    """Tests successful order lookup with normalized ID."""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "order_id": "ORD-1001",
        "customer_name": "Alice Johnson",
        "status": "DELIVERED",
        "total_amount": 149.99,
    }

    mock_collection = MagicMock()
    mock_collection.document.return_value.get.return_value = mock_doc

    with patch("app.database.get_orders_collection", return_value=mock_collection):
        result = tools.lookup_order("  ord-1001  ")

    mock_collection.document.assert_called_once_with("ORD-1001")
    assert result["status"] == "SUCCESS"
    assert result["order"]["order_id"] == "ORD-1001"
    assert result["order"]["customer_name"] == "Alice Johnson"


def test_lookup_order_not_found():
    """Tests lookup for non-existent order."""
    mock_doc = MagicMock()
    mock_doc.exists = False

    mock_collection = MagicMock()
    mock_collection.document.return_value.get.return_value = mock_doc

    with patch("app.database.get_orders_collection", return_value=mock_collection):
        result = tools.lookup_order("ORD-9999")

    assert "error" in result
    assert "was not found in the database" in result["error"]


def test_lookup_order_exception():
    """Tests exception handling during order lookup."""
    mock_collection = MagicMock()
    mock_collection.document.return_value.get.side_effect = RuntimeError(
        "Firestore connection timed out"
    )

    with patch("app.database.get_orders_collection", return_value=mock_collection):
        result = tools.lookup_order("ORD-1001")

    assert "error" in result
    assert "Database error looking up order 'ORD-1001'" in result["error"]
    assert "Firestore connection timed out" in result["error"]


# ---------------------------------------------------------------------------
# Tests for check_inventory
# ---------------------------------------------------------------------------


def test_check_inventory_by_exact_sku():
    """Tests inventory check when querying by exact SKU."""
    mock_sku_doc = MagicMock()
    mock_sku_doc.exists = True
    mock_sku_doc.to_dict.return_value = {
        "sku": "SKU-HEADPHONES-01",
        "name": "Wireless Noise-Canceling Headphones",
        "stock": 42,
        "price": 149.99,
        "location": "Warehouse-East",
    }

    mock_collection = MagicMock()
    mock_collection.document.return_value.get.return_value = mock_sku_doc

    with patch("app.database.get_inventory_collection", return_value=mock_collection):
        result = tools.check_inventory("  sku-headphones-01  ")

    mock_collection.document.assert_called_once_with("SKU-HEADPHONES-01")
    assert result["status"] == "SUCCESS"
    assert result["product"]["sku"] == "SKU-HEADPHONES-01"
    assert result["product"]["stock"] == 42


def test_check_inventory_by_name_keyword():
    """Tests inventory check keyword matching across items when SKU is not found."""
    mock_sku_doc = MagicMock()
    mock_sku_doc.exists = False

    item1_doc = MagicMock()
    item1_doc.to_dict.return_value = {
        "sku": "SKU-HEADPHONES-01",
        "name": "Wireless Noise-Canceling Headphones",
        "stock": 42,
        "price": 149.99,
    }
    item2_doc = MagicMock()
    item2_doc.to_dict.return_value = {
        "sku": "SKU-CABLE-01",
        "name": "USB-C Fast Charging Cable",
        "stock": 100,
        "price": 19.99,
    }

    mock_collection = MagicMock()
    mock_collection.document.return_value.get.return_value = mock_sku_doc
    mock_collection.stream.return_value = [item1_doc, item2_doc]

    with patch("app.database.get_inventory_collection", return_value=mock_collection):
        result = tools.check_inventory("Headphones")

    assert result["status"] == "SUCCESS"
    assert len(result["matches"]) == 1
    assert result["matches"][0]["sku"] == "SKU-HEADPHONES-01"


def test_check_inventory_not_found():
    """Tests inventory check when neither SKU nor keyword matches."""
    mock_sku_doc = MagicMock()
    mock_sku_doc.exists = False

    item1_doc = MagicMock()
    item1_doc.to_dict.return_value = {
        "sku": "SKU-CABLE-01",
        "name": "USB-C Fast Charging Cable",
    }

    mock_collection = MagicMock()
    mock_collection.document.return_value.get.return_value = mock_sku_doc
    mock_collection.stream.return_value = [item1_doc]

    with patch("app.database.get_inventory_collection", return_value=mock_collection):
        result = tools.check_inventory("Smart Watch")

    assert "error" in result
    assert "No product found matching 'Smart Watch'" in result["error"]


def test_check_inventory_exception():
    """Tests exception handling during inventory check."""
    mock_collection = MagicMock()
    mock_collection.document.return_value.get.side_effect = RuntimeError("DB error")

    with patch("app.database.get_inventory_collection", return_value=mock_collection):
        result = tools.check_inventory("SKU-001")

    assert "error" in result
    assert "Database error checking inventory for 'SKU-001'" in result["error"]


# ---------------------------------------------------------------------------
# Tests for process_refund
# ---------------------------------------------------------------------------


def test_process_refund_success():
    """Tests successful refund processing within the 30-day window."""
    today = datetime.datetime.now(datetime.UTC).date()
    delivery_date = (today - datetime.timedelta(days=10)).isoformat()

    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "order_id": "ORD-1001",
        "status": "DELIVERED",
        "refund_status": "NONE",
        "total_amount": 149.99,
        "delivery_date": delivery_date,
    }

    mock_order_ref = MagicMock()
    mock_order_ref.get.return_value = mock_doc

    mock_orders_col = MagicMock()
    mock_orders_col.document.return_value = mock_order_ref

    mock_refund_ref = MagicMock()
    mock_refunds_col = MagicMock()
    mock_refunds_col.document.return_value = mock_refund_ref

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.batch.return_value = mock_batch

    with (
        patch("app.database.get_orders_collection", return_value=mock_orders_col),
        patch("app.database.get_refunds_collection", return_value=mock_refunds_col),
        patch("app.database.get_db", return_value=mock_db),
    ):
        result = tools.process_refund(
            "ord-1001", "Defective ear pad", 149.99
        )

    assert result["status"] == "APPROVED"
    assert result["order_id"] == "ORD-1001"
    assert result["refund_amount"] == 149.99
    assert result["reason"] == "Defective ear pad"
    assert result["transaction_id"].startswith("REF-")
    assert "Refund of $149.99 successfully issued" in result["message"]

    # Verify atomic batch calls
    mock_batch.update.assert_called_once()
    mock_batch.set.assert_called_once()
    mock_batch.commit.assert_called_once()


def test_process_refund_order_not_found():
    """Tests refund failure when order does not exist."""
    mock_doc = MagicMock()
    mock_doc.exists = False

    mock_order_ref = MagicMock()
    mock_order_ref.get.return_value = mock_doc

    mock_orders_col = MagicMock()
    mock_orders_col.document.return_value = mock_order_ref

    with patch("app.database.get_orders_collection", return_value=mock_orders_col):
        result = tools.process_refund("ORD-9999", "Item broken", 50.0)

    assert "error" in result
    assert "Order 'ORD-9999' not found" in result["error"]


def test_process_refund_not_delivered():
    """Tests refund rejection when order is not in DELIVERED status."""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "order_id": "ORD-1002",
        "status": "SHIPPED",
        "total_amount": 100.0,
    }

    mock_order_ref = MagicMock()
    mock_order_ref.get.return_value = mock_doc
    mock_orders_col = MagicMock()
    mock_orders_col.document.return_value = mock_order_ref

    with patch("app.database.get_orders_collection", return_value=mock_orders_col):
        result = tools.process_refund("ORD-1002", "Want to cancel", 100.0)

    assert "error" in result
    assert "status is 'SHIPPED'" in result["error"]
    assert "Only DELIVERED orders are eligible" in result["error"]


def test_process_refund_already_refunded():
    """Tests refund rejection when order has already been refunded."""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "order_id": "ORD-1003",
        "status": "DELIVERED",
        "refund_status": "REFUNDED",
        "total_amount": 100.0,
    }

    mock_order_ref = MagicMock()
    mock_order_ref.get.return_value = mock_doc
    mock_orders_col = MagicMock()
    mock_orders_col.document.return_value = mock_order_ref

    with patch("app.database.get_orders_collection", return_value=mock_orders_col):
        result = tools.process_refund("ORD-1003", "Defective", 100.0)

    assert "error" in result
    assert "has already been refunded" in result["error"]


def test_process_refund_invalid_amount_zero_or_negative():
    """Tests refund rejection when amount is zero or negative."""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "order_id": "ORD-1004",
        "status": "DELIVERED",
        "refund_status": "NONE",
        "total_amount": 100.0,
    }

    mock_order_ref = MagicMock()
    mock_order_ref.get.return_value = mock_doc
    mock_orders_col = MagicMock()
    mock_orders_col.document.return_value = mock_order_ref

    with patch("app.database.get_orders_collection", return_value=mock_orders_col):
        result_zero = tools.process_refund("ORD-1004", "Reason", 0.0)
        result_neg = tools.process_refund("ORD-1004", "Reason", -10.0)

    assert "error" in result_zero
    assert "Invalid refund amount $0.00" in result_zero["error"]
    assert "error" in result_neg
    assert "Invalid refund amount $-10.00" in result_neg["error"]


def test_process_refund_invalid_amount_exceeding_total():
    """Tests refund rejection when requested amount exceeds total order amount."""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "order_id": "ORD-1005",
        "status": "DELIVERED",
        "refund_status": "NONE",
        "total_amount": 50.0,
    }

    mock_order_ref = MagicMock()
    mock_order_ref.get.return_value = mock_doc
    mock_orders_col = MagicMock()
    mock_orders_col.document.return_value = mock_order_ref

    with patch("app.database.get_orders_collection", return_value=mock_orders_col):
        result = tools.process_refund("ORD-1005", "Reason", 50.01)

    assert "error" in result
    assert "Must be between $0.01 and the order total $50.00" in result["error"]


def test_process_refund_exceeds_30_day_window():
    """Tests refund rejection when delivery date is older than 30 days."""
    today = datetime.datetime.now(datetime.UTC).date()
    past_delivery_date = (today - datetime.timedelta(days=35)).isoformat()

    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "order_id": "ORD-1006",
        "status": "DELIVERED",
        "refund_status": "NONE",
        "total_amount": 100.0,
        "delivery_date": past_delivery_date,
    }

    mock_order_ref = MagicMock()
    mock_order_ref.get.return_value = mock_doc
    mock_orders_col = MagicMock()
    mock_orders_col.document.return_value = mock_order_ref

    with patch("app.database.get_orders_collection", return_value=mock_orders_col):
        result = tools.process_refund("ORD-1006", "Reason", 100.0)

    assert "error" in result
    assert "Refunds are only permitted within 30 days" in result["error"]
    assert "35 days ago" in result["error"]


def test_process_refund_fallback_order_date_and_unparseable():
    """Tests refund processing when delivery_date is missing (uses order_date) and invalid date strings."""
    today = datetime.datetime.now(datetime.UTC).date()
    order_date = (today - datetime.timedelta(days=5)).isoformat()

    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "order_id": "ORD-1007",
        "status": "DELIVERED",
        "refund_status": "NONE",
        "total_amount": 100.0,
        "order_date": order_date,
    }

    mock_order_ref = MagicMock()
    mock_order_ref.get.return_value = mock_doc
    mock_orders_col = MagicMock()
    mock_orders_col.document.return_value = mock_order_ref

    mock_refund_ref = MagicMock()
    mock_refunds_col = MagicMock()
    mock_refunds_col.document.return_value = mock_refund_ref

    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.batch.return_value = mock_batch

    with (
        patch("app.database.get_orders_collection", return_value=mock_orders_col),
        patch("app.database.get_refunds_collection", return_value=mock_refunds_col),
        patch("app.database.get_db", return_value=mock_db),
    ):
        result = tools.process_refund("ORD-1007", "Reason", 100.0)

    assert result["status"] == "APPROVED"


def test_process_refund_exception_handling():
    """Tests database error handling during refund processing."""
    mock_order_ref = MagicMock()
    mock_order_ref.get.side_effect = RuntimeError("Firestore unavailable")

    mock_orders_col = MagicMock()
    mock_orders_col.document.return_value = mock_order_ref

    with patch("app.database.get_orders_collection", return_value=mock_orders_col):
        result = tools.process_refund("ORD-1001", "Reason", 50.0)

    assert "error" in result
    assert "Database error processing refund for 'ORD-1001'" in result["error"]


# ---------------------------------------------------------------------------
# Tests for search_product_faq
# ---------------------------------------------------------------------------


def test_search_product_faq_exact_topic():
    """Tests FAQ lookup for an exact topic match."""
    mock_faq_doc = MagicMock()
    mock_faq_doc.exists = True
    mock_faq_doc.to_dict.return_value = {
        "topic": "return_policy",
        "details": "Delivered items can be returned within 30 days for a full refund.",
    }

    mock_col = MagicMock()
    mock_col.document.return_value.get.return_value = mock_faq_doc

    with patch("app.database.get_faqs_collection", return_value=mock_col):
        result = tools.search_product_faq("return policy")

    mock_col.document.assert_called_once_with("return_policy")
    assert result["topic"] == "return_policy"
    assert "within 30 days" in result["details"]


def test_search_product_faq_substring_topic():
    """Tests FAQ lookup via substring search when exact doc ID does not match."""
    mock_faq_doc_exact = MagicMock()
    mock_faq_doc_exact.exists = False

    faq_item = MagicMock()
    faq_item.id = "warranty_coverage"
    faq_item.to_dict.return_value = {
        "topic": "warranty_coverage",
        "details": "All electronics include a standard 1-year manufacturer warranty.",
    }

    mock_col = MagicMock()
    mock_col.document.return_value.get.return_value = mock_faq_doc_exact
    mock_col.stream.return_value = [faq_item]

    with patch("app.database.get_faqs_collection", return_value=mock_col):
        result = tools.search_product_faq("warranty")

    assert result["topic"] == "warranty_coverage"
    assert "1-year manufacturer warranty" in result["details"]


def test_search_product_faq_fallback():
    """Tests FAQ lookup fallback when no topic matches."""
    mock_faq_doc_exact = MagicMock()
    mock_faq_doc_exact.exists = False

    faq_item = MagicMock()
    faq_item.id = "shipping_policy"
    faq_item.to_dict.return_value = {
        "topic": "shipping_policy",
        "details": "Standard shipping takes 3-5 business days.",
    }

    mock_col = MagicMock()
    mock_col.document.return_value.get.return_value = mock_faq_doc_exact
    mock_col.stream.return_value = [faq_item]

    with patch("app.database.get_faqs_collection", return_value=mock_col):
        result = tools.search_product_faq("catering services")

    assert result["topic"] == "catering services"
    assert "shipping_policy" in result["available_topics"]
    assert "support@cymbalretail.example.com" in result["details"]


def test_search_product_faq_exception_handling():
    """Tests exception handling during FAQ search."""
    mock_col = MagicMock()
    mock_col.document.return_value.get.side_effect = RuntimeError("Firestore failure")

    with patch("app.database.get_faqs_collection", return_value=mock_col):
        result = tools.search_product_faq("shipping")

    assert "error" in result
    assert "Database error searching FAQ for 'shipping'" in result["error"]
