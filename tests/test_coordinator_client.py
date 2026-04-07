"""Test the Coordinator Agent through A2A."""

import asyncio
import os

from a2a_test_client import run_a2a_client

AGENT_HOST = os.getenv("HOST_COORDINATOR", "localhost")
AGENT_PORT = int(os.getenv("PORT_COORDINATOR", "10000"))

if __name__ == "__main__":
    asyncio.run(run_a2a_client(
        AGENT_HOST,
        AGENT_PORT,
        "Can you help me draft a message for TD Reply GmbH from Berlin, Germany (https://tdreply.de/) regarding a partnership proposal?",
    ))
