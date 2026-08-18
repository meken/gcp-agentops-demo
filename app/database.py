import os

from google.cloud import firestore
from google.cloud.firestore import CollectionReference

# Global cached Firestore client instance
_db_client: firestore.Client | None = None

# Collection name constants
COLLECTION_ORDERS = "orders"
COLLECTION_INVENTORY = "inventory"
COLLECTION_FAQS = "faqs"
COLLECTION_REFUNDS = "refunds"


def get_db() -> firestore.Client:
    """Returns a singleton Firestore client instance.

    Uses environment variables for configuration:
    - GOOGLE_CLOUD_PROJECT: Project ID
    - FIRESTORE_DATABASE: Optional named database ID (defaults to '(default)')
    - FIRESTORE_EMULATOR_HOST: Optional emulator host for local mock/testing
    """
    global _db_client
    if _db_client is None:
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        database = os.getenv("FIRESTORE_DATABASE", "(default)")
        _db_client = firestore.Client(project=project, database=database)
    return _db_client


def get_orders_collection() -> CollectionReference:
    return get_db().collection(COLLECTION_ORDERS)


def get_inventory_collection() -> CollectionReference:
    return get_db().collection(COLLECTION_INVENTORY)


def get_faqs_collection() -> CollectionReference:
    return get_db().collection(COLLECTION_FAQS)


def get_refunds_collection() -> CollectionReference:
    return get_db().collection(COLLECTION_REFUNDS)


def reset_db_client() -> None:
    """Resets the cached Firestore client instance (useful in tests)."""
    global _db_client
    _db_client = None
