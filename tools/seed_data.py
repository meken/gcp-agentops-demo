
import argparse
import datetime
import os
import sys

from typing import Any, Dict, Optional

from google.cloud import firestore

# Firestore Collection Names
COLLECTION_ORDERS = "orders"
COLLECTION_INVENTORY = "inventory"
COLLECTION_FAQS = "faqs"

# Reference default base date (useful for deterministic tests)
DEFAULT_REFERENCE_DATE = datetime.date(2026, 8, 18)


def get_firestore_client(
    project: Optional[str] = None,
    database: Optional[str] = None,
) -> firestore.Client:
    """Creates a Firestore client without depending on application modules.

    Args:
        project: Optional GCP Project ID (falls back to GOOGLE_CLOUD_PROJECT / GCP_PROJECT env vars).
        database: Optional named Firestore database ID (defaults to '(default)').

    Returns:
        A Google Cloud Firestore Client instance.
    """
    proj = project or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    db_name = database or os.getenv("FIRESTORE_DATABASE", "(default)")
    return firestore.Client(project=proj, database=db_name)


def get_seed_orders(base_date: Optional[datetime.date] = None) -> Dict[str, Dict[str, Any]]:
    """Generates order seed data with parameterized relative dates.

    Args:
        base_date: Reference date for relative date calculation.
                   Defaults to today (or DEFAULT_REFERENCE_DATE if specified).

    Returns:
        Dictionary mapping order IDs to order record dictionaries.
    """
    ref = base_date or datetime.date.today()

    return {
        "ORD-1001": {
            "order_id": "ORD-1001",
            "customer_id": "CUST-501",
            "customer_name": "Alice Johnson",
            "status": "DELIVERED",
            "order_date": (ref - datetime.timedelta(days=17)).isoformat(),
            "delivery_date": (ref - datetime.timedelta(days=13)).isoformat(),
            "items": [
                {
                    "sku": "SKU-HEADPHONES-01",
                    "name": "Wireless Noise Cancelling Headphones",
                    "qty": 1,
                    "price": 199.99,
                }
            ],
            "total_amount": 199.99,
            "refund_status": "NONE",
        },
        "ORD-1002": {
            "order_id": "ORD-1002",
            "customer_id": "CUST-502",
            "customer_name": "Bob Smith",
            "status": "IN_TRANSIT",
            "order_date": (ref - datetime.timedelta(days=3)).isoformat(),
            "estimated_delivery": (ref + datetime.timedelta(days=2)).isoformat(),
            "items": [
                {
                    "sku": "SKU-KEYBOARD-02",
                    "name": "Ergonomic Mechanical Keyboard",
                    "qty": 1,
                    "price": 129.50,
                },
                {
                    "sku": "SKU-MOUSE-03",
                    "name": "Precision Wireless Mouse",
                    "qty": 1,
                    "price": 49.99,
                },
            ],
            "total_amount": 179.49,
            "refund_status": "NONE",
        },
        "ORD-1003": {
            "order_id": "ORD-1003",
            "customer_id": "CUST-503",
            "customer_name": "Carol Danvers",
            "status": "DELIVERED",
            "order_date": (ref - datetime.timedelta(days=39)).isoformat(),
            "delivery_date": (ref - datetime.timedelta(days=35)).isoformat(),
            "items": [
                {
                    "sku": "SKU-SMARTWATCH-04",
                    "name": "Ultra Fitness Smartwatch",
                    "qty": 1,
                    "price": 249.00,
                }
            ],
            "total_amount": 249.00,
            "refund_status": "REFUNDED",
        },
    }


def get_seed_inventory() -> Dict[str, Dict[str, Any]]:
    """Generates product inventory seed data.

    Returns:
        Dictionary mapping SKU identifiers to product inventory dictionaries.
    """
    return {
        "SKU-HEADPHONES-01": {
            "sku": "SKU-HEADPHONES-01",
            "name": "Wireless Noise Cancelling Headphones",
            "stock": 42,
            "warehouse": "us-central1-a",
            "price": 199.99,
        },
        "SKU-KEYBOARD-02": {
            "sku": "SKU-KEYBOARD-02",
            "name": "Ergonomic Mechanical Keyboard",
            "stock": 15,
            "warehouse": "us-east1-b",
            "price": 129.50,
        },
        "SKU-MOUSE-03": {
            "sku": "SKU-MOUSE-03",
            "name": "Precision Wireless Mouse",
            "stock": 88,
            "warehouse": "us-central1-a",
            "price": 49.99,
        },
        "SKU-SMARTWATCH-04": {
            "sku": "SKU-SMARTWATCH-04",
            "name": "Ultra Fitness Smartwatch",
            "stock": 0,
            "warehouse": "us-west1-a",
            "price": 249.00,
        },
    }


def get_seed_faqs() -> Dict[str, Dict[str, Any]]:
    """Generates knowledge base and FAQ seed data.

    Returns:
        Dictionary mapping topic keys to FAQ record dictionaries.
    """
    return {
        "return_policy": {
            "topic": "return_policy",
            "title": "Return Policy",
            "details": (
                "Cymbal Retail offers a 30-day money-back guarantee on all delivered items. "
                "Items must be in original condition."
            ),
        },
        "shipping_policy": {
            "topic": "shipping_policy",
            "title": "Shipping Policy",
            "details": (
                "Standard shipping takes 3-5 business days. Express shipping takes 1-2 business days."
            ),
        },
        "warranty": {
            "topic": "warranty",
            "title": "Warranty",
            "details": (
                "All electronics include a standard 1-year limited manufacturer warranty covering "
                "defects in materials and workmanship."
            ),
        },
        "international_shipping": {
            "topic": "international_shipping",
            "title": "International Shipping",
            "details": "We currently ship to the US, Canada, EU, and UK.",
        },
    }


def get_all_seed_data(base_date: Optional[datetime.date] = None) -> Dict[str, Any]:
    """Returns complete seed dataset across all domains for test fixtures.

    Args:
        base_date: Optional reference date for calculating relative order dates.

    Returns:
        Dictionary containing 'orders', 'inventory', and 'faqs' datasets.
    """
    return {
        "orders": get_seed_orders(base_date),
        "inventory": get_seed_inventory(),
        "faqs": get_seed_faqs(),
    }


def seed_firestore(
    db: Optional[firestore.Client] = None,
    base_date: Optional[datetime.date] = None,
    project: Optional[str] = None,
    database: Optional[str] = None,
) -> Dict[str, int]:
    """Seeds the Firestore database with parameterized initial data.

    Args:
        db: Optional Firestore client instance. If not provided, one will be created.
        base_date: Optional reference date for order timelines.
        project: Optional GCP Project ID when initializing a new client.
        database: Optional named Firestore database ID when initializing a new client.

    Returns:
        Dictionary reporting the number of records inserted per collection.
    """
    client = db or get_firestore_client(project=project, database=database)
    data = get_all_seed_data(base_date)
    counts: Dict[str, int] = {}

    # Seed Orders
    batch = client.batch()
    for order_id, order_data in data["orders"].items():
        doc_ref = client.collection(COLLECTION_ORDERS).document(order_id)
        batch.set(doc_ref, order_data)
    batch.commit()
    counts[COLLECTION_ORDERS] = len(data["orders"])

    # Seed Inventory
    batch = client.batch()
    for sku, product_data in data["inventory"].items():
        doc_ref = client.collection(COLLECTION_INVENTORY).document(sku)
        batch.set(doc_ref, product_data)
    batch.commit()
    counts[COLLECTION_INVENTORY] = len(data["inventory"])

    # Seed FAQs
    batch = client.batch()
    for topic, faq_data in data["faqs"].items():
        doc_ref = client.collection(COLLECTION_FAQS).document(topic)
        batch.set(doc_ref, faq_data)
    batch.commit()
    counts[COLLECTION_FAQS] = len(data["faqs"])

    return counts


def main():
    parser = argparse.ArgumentParser(
        description="Standalone Firestore seed data generator and loader for Cymbal Retail Agent"
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Google Cloud Project ID (default: GOOGLE_CLOUD_PROJECT env var)",
    )
    parser.add_argument(
        "--database",
        default=None,
        help="Firestore database ID (default: FIRESTORE_DATABASE env var or '(default)')",
    )
    parser.add_argument(
        "--base-date",
        type=lambda s: datetime.datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="Base reference date (YYYY-MM-DD) for relative date calculations (default: today)",
    )
    args = parser.parse_args()

    ref_date = args.base_date or datetime.date.today()
    print(f"=== Cymbal Retail Firestore Seeder ===")
    print(f"Base Reference Date: {ref_date}")
    print(f"Target Database: {args.database or os.getenv('FIRESTORE_DATABASE', '(default)')}")
    if args.project:
        print(f"Project ID: {args.project}")
    print()

    try:
        counts = seed_firestore(
            base_date=args.base_date,
            project=args.project,
            database=args.database,
        )
        print("Seeding completed successfully:")
        for col, count in counts.items():
            print(f"  - {col}: {count} documents written")
    except Exception as e:
        print(f"Failed to seed Firestore: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
