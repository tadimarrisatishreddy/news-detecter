import os
import pytest
from ai.gemma_client import default_gemma_client

# Set mock mode during automated pytest test runs for rapid deterministic testing
os.environ["AI_DETECTION_MODE"] = "mock"
default_gemma_client.mode = "mock"


@pytest.fixture(autouse=True)
def configure_test_env():
    default_gemma_client.mode = "mock"
    yield

