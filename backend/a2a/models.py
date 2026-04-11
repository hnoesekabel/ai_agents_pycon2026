"""Data model definitions for A2A"""

from __future__ import annotations

from pydantic import AnyUrl, BaseModel


class AgentEndpoint(BaseModel):
    """Define Agent Endpoint Model."""

    name: str
    url: AnyUrl
    protocol: str  # e.g. "stream/text", "sse", "ndjson"
    method: str  # "POST", "GET"


class AgentCard(BaseModel):
    """Define the A2A Agent Card."""

    agent_id: str
    name: str
    version: str
    description: str
    capabilities: list[str]
    endpoints: list[AgentEndpoint]
    owner: str | None = None
    tags: list[str] = []


class DiscoveryRequest(BaseModel):
    """Define model for A2A Discovery Request."""

    query: str | None = None
    required_capabilities: list[str] | None = []


class DiscoveryResponse(BaseModel):
    """Define model for A2A Discovery Response."""

    agents: list[AgentCard] | None = None
