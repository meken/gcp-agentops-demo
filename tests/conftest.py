import copy
import datetime

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from google.cloud import firestore

from retail_agent import database
from tests import seed_data


@pytest.fixture(scope="session")
def fixed_base_date() -> datetime.date:
    """Provides a fixed reference date (2026-08-18) for deterministic date calculations."""
    return datetime.date(2026, 8, 18)


@pytest.fixture(scope="session")
def seed_dataset(fixed_base_date: datetime.date) -> dict[str, Any]:
    """Provides raw dictionary of all seed data (orders, inventory, faqs)."""
    return seed_data.get_all_seed_data(base_date=fixed_base_date)


@pytest.fixture(scope="module")
def db_client() -> Generator[firestore.Client]:
    """Provides an active Firestore client for database tests."""
    database.reset_db_client()
    client = database.get_db()
    yield client
    database.reset_db_client()


@pytest.fixture
def seeded_db(
    db_client: firestore.Client, fixed_base_date: datetime.date
) -> firestore.Client:
    """Seeds the Firestore database before each test and returns the client instance."""
    seed_data.seed_firestore(db=db_client, base_date=fixed_base_date)
    return db_client


@pytest.fixture(autouse=True)
def mock_db_for_evals(request: pytest.FixtureRequest, fixed_base_date: datetime.date):
    """Automatically provides an in-memory Firestore mock for evaluation tests.

    Executes real tool Python code without external database side-effects or state leakage.
    """
    if "eval" not in [marker.name for marker in request.node.iter_markers()]:
        yield
        return

    seed_orders = seed_data.get_seed_orders(base_date=fixed_base_date)
    seed_inv = seed_data.get_seed_inventory()
    seed_faqs = seed_data.get_seed_faqs()

    # Mock Orders Collection: doc_ref.get() returns snapshot
    def mock_order_doc(doc_id: str):
        doc_ref = MagicMock()
        snapshot = MagicMock()
        data = seed_orders.get(doc_id)
        snapshot.exists = data is not None
        snapshot.to_dict.return_value = copy.deepcopy(data) if data else None
        doc_ref.get.return_value = snapshot
        return doc_ref

    mock_orders_col = MagicMock()
    mock_orders_col.document.side_effect = mock_order_doc

    # Mock Inventory Collection: doc_ref.get() and stream()
    def mock_inv_doc(sku: str):
        doc_ref = MagicMock()
        snapshot = MagicMock()
        data = seed_inv.get(sku)
        snapshot.exists = data is not None
        snapshot.to_dict.return_value = copy.deepcopy(data) if data else None
        doc_ref.get.return_value = snapshot
        return doc_ref

    mock_inv_col = MagicMock()
    mock_inv_col.document.side_effect = mock_inv_doc

    def mock_inv_stream():
        docs = []
        for item in seed_inv.values():
            d = MagicMock()
            d.to_dict.return_value = copy.deepcopy(item)
            docs.append(d)
        return docs

    mock_inv_col.stream.side_effect = mock_inv_stream

    # Mock FAQs Collection: doc_ref.get() and stream()
    def mock_faq_doc(topic: str):
        doc_ref = MagicMock()
        snapshot = MagicMock()
        data = seed_faqs.get(topic)
        snapshot.exists = data is not None
        snapshot.to_dict.return_value = copy.deepcopy(data) if data else None
        doc_ref.get.return_value = snapshot
        return doc_ref

    mock_faqs_col = MagicMock()
    mock_faqs_col.document.side_effect = mock_faq_doc

    def mock_faq_stream():
        docs = []
        for key, val in seed_faqs.items():
            d = MagicMock()
            d.id = key
            d.to_dict.return_value = copy.deepcopy(val)
            docs.append(d)
        return docs

    mock_faqs_col.stream.side_effect = mock_faq_stream

    # Mock Refunds Collection & Batch Transaction
    mock_refunds_col = MagicMock()
    mock_refund_doc = MagicMock()
    mock_refunds_col.document.return_value = mock_refund_doc

    mock_db = MagicMock()
    mock_batch = MagicMock()
    mock_db.batch.return_value = mock_batch

    with (
        patch("retail_agent.database.get_orders_collection", return_value=mock_orders_col),
        patch("retail_agent.database.get_inventory_collection", return_value=mock_inv_col),
        patch("retail_agent.database.get_faqs_collection", return_value=mock_faqs_col),
        patch("retail_agent.database.get_refunds_collection", return_value=mock_refunds_col),
        patch("retail_agent.database.get_db", return_value=mock_db),
    ):
        yield
