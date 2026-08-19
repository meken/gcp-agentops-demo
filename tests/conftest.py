import datetime

from collections.abc import Generator
from typing import Any

import pytest

from google.cloud import firestore

from app import database
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
def db_client() -> Generator[firestore.Client, None, None]:
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
