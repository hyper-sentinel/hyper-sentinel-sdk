"""Shared fixtures for sentinel-sdk integration tests."""

import os
import time

import pytest

from sentinel.api.client import SentinelAPI as SentinelClient

PROD_URL = "https://sentinel-api-281199879392.us-south1.run.app"


@pytest.fixture(scope="session")
def base_url():
    return os.environ.get("SENTINEL_TEST_URL", PROD_URL)


@pytest.fixture(scope="session")
def test_creds():
    """Unique credentials for this test run."""
    ts = int(time.time())
    return {
        "email": f"sdk-test-{ts}@test.sentinel.dev",
        "password": f"testpass-{ts}",
        "name": "SDK Test Runner",
    }


@pytest.fixture(scope="session")
def client(base_url, test_creds):
    """Authenticated SentinelClient — registers a fresh account once per session."""
    c = SentinelClient(base_url=base_url, timeout=30.0)
    c.register(**test_creds)
    yield c
    c.close()


@pytest.fixture(scope="session")
def ai_key():
    """AI provider key from env — skip LLM tests if not set."""
    key = os.environ.get("SENTINEL_TEST_AI_KEY", "")
    if not key:
        pytest.skip("SENTINEL_TEST_AI_KEY not set")
    return key
