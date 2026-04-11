"""Test the Outreach Agent through A2A."""

import asyncio
import os

from a2a_test_client import run_a2a_client

AGENT_HOST = os.getenv("HOST_OUTREACH", "localhost")
AGENT_PORT = int(os.getenv("PORT_OUTREACH", "10002"))

if __name__ == "__main__":
    asyncio.run(run_a2a_client(
        AGENT_HOST,
        AGENT_PORT,
        "Can you please draft an email to the CEO of TD Reply GmbH from Berlin, Germany (https://tdreply.de/)?",
    ))
