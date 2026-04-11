"""Dependency functions for API, e.g. username extraction."""

import logging
from typing import Annotated

from fastapi import Header, HTTPException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_token_header(x_token: Annotated[str, Header()]):
    """Validate X-Token header is set and correct."""
    if x_token != "fake-super-secret-token":
        raise HTTPException(status_code=400, detail="X-Token header invalid")


async def get_userid() -> int:
    """Extract user ID from header."""
    return 1  # TODO: add proper user handling
