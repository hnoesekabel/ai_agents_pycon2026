# Build Agentic System with Python, LangGraph, MCP and A2A

## Introduction

Code repository for the PyCon 2026 presentation.

## Setup

You need `uv` installed; if this is not the case, use curl to install it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Clone the repository locally on your machine, create a Python environment, and install required libraries:

```sh
git clone git@github.com:hnoesekabel/ai_agents_pycon2026.git
cd ai_agents_pycon2026
uv venv --python 3.14
source .venv/bin/activate
uv sync
```

Additionally, install Playwright for the Crawl4AI MCP server:

```bash
playwright install
```

## Configuration

Add API keys to the `.env` file following the template of `.env.example`, either rename or copy the example file.

### OpenAI

Set `OPENAI_API_KEY` to your OpenAI key that you can create at <https://platform.openai.com/api-keys>.

The agents use two model settings in `.env`:

- `AGENT_MODEL` — the model used by agents (default: `openai:gpt-4.1-mini`)
- `CHAT_MODEL` — the model used for chat completions (default: `gpt-4.1-mini`)

### Google Custom Search

Add a Google Cloud API key for Custom Search and the CSE ID to the `.env` file as `GOOGLE_API_KEY` and `GOOGLE_CSE_ID`.

To create the API key for the Google search,

1. go to <https://console.cloud.google.com/> and log in with your Google account
2. in the top left, click the project box
3. click on "New project", give the project a name, and then "Create"
4. wait for the project to be created, then click "select project"
5. under "Quick access" click "APIs & Services"
6. then the button "+ Enable APIs and services"
7. search for "custom search api" then select "Custom Search API" from the results
8. click "Enable" then on "Credentials" in the menu on the left
9. click "Create credentials" at the top to open the dropdown, select "API Key"
10. give it a name and set restrictions as needed, then click "Create"
11. copy the API key to `.env` as `GOOGLE_API_KEY`
12. next go to <https://programmablesearchengine.google.com/u/1/controlpanel/create>
13. add a name, some domains like `*.com`, keep image search / safe search disabled, tick the Captcha, then click "Create" and then "Customize"
14. copy the "Search engine ID" to `.env` as `GOOGLE_CSE_ID`

The free configuration allows for 100 searches per day. If needed, the CSE can be further limited to specific regions (e.g. US), or languages (e.g. EN).

### World News API

To create a free API key with World News, sign up with their service for free, then get your API key at <https://worldnewsapi.com/console/#Profile>. Copy it to `.env` as `WORLD_NEWS_API_KEY`.

### LangSmith (optional)

To enable LangSmith tracing, set `LANGSMITH_API_KEY` in `.env`. The other LangSmith variables (`LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT`, `LANGCHAIN_TRACING_V2`) are preconfigured in `.env.example`.

## Starting

### Command-Line

To start a given agent, backend, or MCP server, run it from the project folder:

```bash
uv run -m mcp_crawl4ai
uv run -m mcp_google
uv run -m mcp_worldnews
uv run -m agent_research
uv run -m agent_outreach
uv run -m agent_coordinator
uv run -m backend
```

This will start the agent / backend / MCP server, and the app will listen on the configured hostname and port.

Note that the MCP servers should be started first, as the research and outreach agent depend on them. And the coordinator agent depends on the research and outreach agent to be running.

### VS Code

If you use VS Code, this repo includes `.vscode/launch.json` with a configuration for each MCP and Agent server, and a compound to start all.

- Open the project in VS Code
- Open the Run and Debug view in VS Code (from the left sidebar)
- Start all servers: choose `All Servers` and press Run. This launches each server in integrated terminals.
- Stop servers via the stop buttons (it will stop all of them currently) or Ctrl+C in their terminals.
- Note that there is a helper script awaiting the startup of MCP-Servers, which will show an additional terminal for a few seconds

## Running

If you want to interact with the Coordinator Agent through the FastAPI interface, start the backend server and run, for example:

```bash
curl -X POST -H "Content-Type: application/json" -d '{"query": "What can you tell me about TD Reply?"}' http://localhost:8080/api/agent
curl -X POST -H "Content-Type: application/json" -d '{"query": "Who is the CEO of Anthropic?"}' http://localhost:8080/api/agent
curl http://localhost:8080/api/chat_history
```

The API is running on 'localhost` on port 8080, and exposes `api/agent` endpoint for agent communication, and `api/chat_history` for the stored chat history.

If you want to test or query one agent specifically, you can use the following scripts in the tests folder:

```bash
uv run tests/test_coordinator_client.py
uv run tests/test_outreach_client.py
uv run tests/test_research_client.py
```

## Testing

You can run the automated tests with `python -m pytest tests/ -v`.

## Caveats

This is a demo implementation to show MCP and A2A protocol use. This code is not intended for production use.

Be aware that `backend/api/dependencies.py` contains the placehoder of a static header token check, and a placeholder for user management. Right now, all requests are accepted, and the user ID assigned to each request will always be 1.
