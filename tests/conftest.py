"""
Pytest fixtures for sugar-sdk tests.
"""
import pytest
import os
from dotenv import load_dotenv
from sugar import AsyncBaseChain, BaseChain

# Load .env file before running tests
load_dotenv()


@pytest.fixture
async def base_chain():
    """Base chain instance for testing"""
    async with AsyncBaseChain() as chain:
        yield chain


@pytest.fixture
def sync_base_chain():
    """Sync Base chain instance for testing"""
    with BaseChain() as chain:
        yield chain
