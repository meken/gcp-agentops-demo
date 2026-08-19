import os

from pathlib import Path

import dotenv
import pytest

from google.adk.evaluation.agent_evaluator import AgentEvaluator

EVALS_DIR = os.path.join(os.path.dirname(__file__), "evals")
AGENT_MODULE = "retail_agent.agent"

# Ensure environment variables from retail_agent/.env are loaded for Vertex AI / GenAI credentials
dotenv.load_dotenv(Path(__file__).parent.parent / "retail_agent" / ".env")

pytestmark = pytest.mark.eval


@pytest.mark.asyncio
async def test_eval_order_lookups():
    """Tests order lookup inquiries trigger lookup_order tool and return accurate status."""
    await AgentEvaluator.evaluate(
        agent_module=AGENT_MODULE,
        eval_dataset_file_path_or_dir=os.path.join(
            EVALS_DIR, "01_order_status.test.json"
        ),
        print_detailed_results=True,
    )


@pytest.mark.asyncio
async def test_eval_inventory_inquiries():
    """Tests product inventory stock inquiries trigger check_inventory tool."""
    await AgentEvaluator.evaluate(
        agent_module=AGENT_MODULE,
        eval_dataset_file_path_or_dir=os.path.join(
            EVALS_DIR, "02_inventory_inquiry.test.json"
        ),
        print_detailed_results=True,
    )


@pytest.mark.asyncio
async def test_eval_store_faqs():
    """Tests return policy and warranty inquiries trigger search_product_faq tool."""
    await AgentEvaluator.evaluate(
        agent_module=AGENT_MODULE,
        eval_dataset_file_path_or_dir=os.path.join(
            EVALS_DIR, "03_store_faqs.test.json"
        ),
        print_detailed_results=True,
    )


@pytest.mark.asyncio
async def test_eval_refund_workflows():
    """Tests refund request handling according to store policies."""
    await AgentEvaluator.evaluate(
        agent_module=AGENT_MODULE,
        eval_dataset_file_path_or_dir=os.path.join(
            EVALS_DIR, "04_refund_processing.test.json"
        ),
        print_detailed_results=True,
    )


