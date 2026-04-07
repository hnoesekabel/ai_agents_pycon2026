"""Test the Research Agent through A2A."""

import asyncio
import os

from a2a_test_client import run_a2a_client

AGENT_HOST = os.getenv("HOST_RESEARCH", "localhost")
AGENT_PORT = int(os.getenv("PORT_RESEARCH", "10001"))

if __name__ == "__main__":
    asyncio.run(run_a2a_client(
        AGENT_HOST,
        AGENT_PORT,
        "Will TD Reply GmbH from Berlin, Germany (https://tdreply.de/) be present at the PyCon 2026 in Darmstadt, Germany?",
    ))
