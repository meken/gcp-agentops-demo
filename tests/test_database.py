import datetime
from collections.abc import Generator

import pytest
from google.cloud import firestore

from app import database, tools

from . import seed_data

# Marking all tests in this file to be integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def db_client() -> Generator[firestore.Client, None, None]:
    """Provides an active Firestore client for integration tests."""
    database.reset_db_client()
    client = database.get_db()
    yield client
    database.reset_db_client()


@pytest.fixture(autouse=True)
def seed_test_data(db_client: firestore.Client) -> None:
    """Seeds the database before each test to guarantee a deterministic state."""
    # Use fixed base date for deterministic date arithmetic
    base_date = datetime.date(2026, 8, 18)
    seed_data.seed_firestore(db=db_client, base_date=base_date)


# ---------------------------------------------------------------------------
# Integration Tests: Order Lookups & State
# ---------------------------------------------------------------------------


def test_order_lookup_real_database_records():
    """Tests looking up existing and non-existing orders in Firestore."""
    # Lookup delivered order
    result = tools.lookup_order("ORD-1001")
    assert result["status"] == "SUCCESS"
    order = result["order"]
    assert order["order_id"] == "ORD-1001"
    assert order["customer_name"] == "Alice Johnson"
    assert order["status"] == "DELIVERED"
    assert order["total_amount"] == 199.99
    assert order["refund_status"] == "NONE"
    assert len(order["items"]) == 1
    assert order["items"][0]["sku"] == "SKU-HEADPHONES-01"

    # Lookup in-transit order
    result_transit = tools.lookup_order("ORD-1002")
    assert result_transit["status"] == "SUCCESS"
    assert result_transit["order"]["status"] == "IN_TRANSIT"

    # Non-existent order
    result_missing = tools.lookup_order("ORD-NONEXISTENT-999")
    assert "error" in result_missing
    assert "was not found in the database" in result_missing["error"]


# ---------------------------------------------------------------------------
# Integration Tests: Atomic Refund Transactions & Persistence
# ---------------------------------------------------------------------------


def test_refund_atomic_transaction_workflow(db_client: firestore.Client):
    """Tests full refund lifecycle: approval, Firestore batch mutation, audit record creation, and duplicate rejection."""
    # 1. Verify initial order state in database
    order_ref = db_client.collection("orders").document("ORD-1001")
    initial_order = order_ref.get().to_dict()
    assert initial_order is not None
    assert initial_order.get("refund_status") == "NONE"

    # 2. Process refund for full amount
    refund_result = tools.process_refund(
        order_id="ORD-1001",
        reason="Defective sound in left earbud",
        amount=199.99,
    )
    assert refund_result["status"] == "APPROVED"
    assert refund_result["order_id"] == "ORD-1001"
    assert refund_result["refund_amount"] == 199.99
    tx_id = refund_result["transaction_id"]
    assert tx_id.startswith("REF-")

    # 3. Verify order document in Firestore was atomically updated
    updated_order = order_ref.get().to_dict()
    assert updated_order is not None
    assert updated_order["refund_status"] == "REFUNDED"
    assert updated_order["last_refund_tx"] == tx_id

    # 4. Verify new audit document exists in refunds collection
    refund_doc_ref = db_client.collection("refunds").document(tx_id)
    refund_record = refund_doc_ref.get().to_dict()
    assert refund_record is not None
    assert refund_record["transaction_id"] == tx_id
    assert refund_record["order_id"] == "ORD-1001"
    assert refund_record["refund_amount"] == 199.99
    assert refund_record["reason"] == "Defective sound in left earbud"
    assert refund_record["status"] == "APPROVED"
    assert "timestamp" in refund_record

    # 5. Verify subsequent refund attempt is rejected by the live database state
    duplicate_attempt = tools.process_refund(
        order_id="ORD-1001",
        reason="Attempting second refund",
        amount=199.99,
    )
    assert "error" in duplicate_attempt
    assert "already been refunded" in duplicate_attempt["error"]


def test_refund_business_rules_against_live_database():
    """Tests that business rules are enforced based on live order properties in Firestore."""
    # Cannot refund IN_TRANSIT order (ORD-1002)
    in_transit_result = tools.process_refund(
        order_id="ORD-1002",
        reason="Changed my mind",
        amount=179.49,
    )
    assert "error" in in_transit_result
    assert "status is 'IN_TRANSIT'" in in_transit_result["error"]
    assert "Only DELIVERED orders are eligible" in in_transit_result["error"]

    # Cannot refund order older than 30 days (ORD-1003 was delivered 35 days ago relative to seed date)
    expired_result = tools.process_refund(
        order_id="ORD-1003",
        reason="Does not fit",
        amount=249.00,
    )
    assert "error" in expired_result
    # ORD-1003 in seed data is already REFUNDED and delivered > 30 days ago
    assert any(
        msg in expired_result["error"]
        for msg in ["already been refunded", "within 30 days"]
    )


# ---------------------------------------------------------------------------
# Integration Tests: Inventory Queries & Streaming Filters
# ---------------------------------------------------------------------------


def test_inventory_query_and_streaming_search():
    """Tests exact SKU lookup and fallback keyword search across live Firestore inventory documents."""
    # 1. Exact SKU lookup
    exact_res = tools.check_inventory("SKU-KEYBOARD-02")
    assert exact_res["status"] == "SUCCESS"
    product = exact_res["product"]
    assert product["sku"] == "SKU-KEYBOARD-02"
    assert product["name"] == "Ergonomic Mechanical Keyboard"
    assert product["stock"] == 15
    assert product["price"] == 129.50

    # 2. Case-insensitive keyword search via streaming collection
    keyword_res = tools.check_inventory("mouse")
    assert keyword_res["status"] == "SUCCESS"
    matches = keyword_res["matches"]
    assert len(matches) >= 1
    matched_skus = [m["sku"] for m in matches]
    assert "SKU-MOUSE-03" in matched_skus

    # 3. Non-existent product query
    missing_res = tools.check_inventory("Wireless Gaming Monitor 4K")
    assert "error" in missing_res
    assert "No product found matching" in missing_res["error"]


# ---------------------------------------------------------------------------
# Integration Tests: FAQ Knowledge Base Search
# ---------------------------------------------------------------------------


def test_faq_retrieval_and_fallback_across_documents():
    """Tests exact and fallback FAQ queries against live Firestore FAQ documents."""
    # Exact lookup
    return_faq = tools.search_product_faq("return policy")
    assert return_faq["topic"] == "return_policy"
    assert "30-day money-back guarantee" in return_faq["details"]

    # Substring lookup
    warranty_faq = tools.search_product_faq("warranty")
    assert warranty_faq["topic"] == "warranty"
    assert "1-year limited manufacturer warranty" in warranty_faq["details"]

    # Unknown topic fallback returning available live topics
    unknown_faq = tools.search_product_faq("catering services")
    assert unknown_faq["topic"] == "catering services"
    assert "return_policy" in unknown_faq["available_topics"]
    assert "support@cymbalretail.example.com" in unknown_faq["details"]
