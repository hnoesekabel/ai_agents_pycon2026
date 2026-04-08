"""Shared pytest fixtures and configuration."""

import pytest


# Configure pytest-asyncio to auto-detect async tests
def pytest_collection_modifyitems(items):
    """Automatically mark async test functions."""
    for item in items:
        if item.get_closest_marker("asyncio") is None:
            if hasattr(item, "function") and hasattr(item.function, "__wrapped__"):
                item.add_marker(pytest.mark.asyncio)
