"""
Pytest fixtures for sugar-sdk tests.
"""
import pytest
import os
from dotenv import load_dotenv
from sugar import AsyncBaseChain

# Load .env file before running tests
load_dotenv()


@pytest.fixture
async def base_chain():
    """Base chain instance for testing"""
    async with AsyncBaseChain() as chain:
        yield chain
