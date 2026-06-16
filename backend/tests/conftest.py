"""
conftest.py — Pytest configuration and fixtures for backend tests.
Forces ENABLE_AUTH = True during testing to ensure the authentication and auth validation logic is fully verified by the test suites.
"""
import pytest

@pytest.fixture(scope="session", autouse=True)
def force_enable_auth_for_tests():
    from config.settings import settings
    settings.ENABLE_AUTH = True
