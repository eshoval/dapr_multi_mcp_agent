# Dapr MCP-Couchbase AI Agent

A natural language chatbot POC that queries a Couchbase database using [Dapr Agents](https://github.com/dapr/python-sdk) and the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

![Architecture](https://img.shields.io/badge/Dapr-1.14+-blue) ![Python](https://img.shields.io/badge/Python-3.10+-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

## Overview

This project demonstrates how to build an AI-powered database assistant that:

- **Accepts natural language queries** from users via a Chainlit web UI
- **Translates questions into SQL++ (N1QL)** queries using an LLM
- **Queries Couchbase** through an MCP server for schema discovery and query execution
- **Returns formatted results** in a conversational manner

### Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Chainlit UI   │────▶│   Dapr Agent    │────▶│   MCP Server    │
│  (Web Browser)  │     │  (LLM + Tools)  │     │  (Couchbase)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  Azure OpenAI   │
                        │   (or OpenAI)   │
                        └─────────────────┘
```

## Prerequisites

- **Python 3.10+**
- **Dapr CLI** installed and initialized ([Install Guide](https://docs.dapr.io/getting-started/install-dapr-cli/))
- **Couchbase MCP Server** running (default: `http://localhost:8000/sse`)
- **Azure OpenAI** or **OpenAI** API access

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/minimal-dapr-cb-mcp-agent.git
cd minimal-dapr-cb-mcp-agent
```

### 2. Create and Activate Virtual Environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/macOS
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file and update it with your settings:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# LLM Configuration
DAPR_LLM_COMPONENT_DEFAULT=azure-openai  # or "openai"
DAPR_LLM_PROVIDER=openai

# MCP Server Configuration
MCP_SERVER_URL=http://localhost:8000/sse

# Couchbase Configuration
CB_BUCKET_NAME=travel-sample
```

### 5. Configure Azure OpenAI Component

Copy the component template and add your credentials:

```bash
cp components/azure-openai.yaml.example components/azure-openai.yaml
```

Edit `components/azure-openai.yaml` with your Azure OpenAI credentials.

### 6. Start the Couchbase MCP Server

Ensure your Couchbase MCP server is running on the configured URL.

### 7. Run the Application

```bash
dapr run -f dapr.yaml
```

The Chainlit UI will be available at **http://localhost:8001**

## Project Structure

```
minimal-dapr-cb-mcp-agent/
├── app.py                 # Main application entry point
├── dapr.yaml              # Dapr multi-app run configuration
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create from .env.example)
├── components/            # Dapr components
│   └── azure-openai.yaml  # LLM component configuration
└── prompts/
    └── system_prompt.txt  # Agent system prompt
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DAPR_LLM_COMPONENT_DEFAULT` | Dapr component name for LLM | `openai` |
| `DAPR_LLM_PROVIDER` | LLM provider type | `openai` |
| `MCP_SERVER_URL` | Couchbase MCP server SSE endpoint | `http://localhost:8000/sse` |
| `CB_BUCKET_NAME` | Couchbase bucket name | `travel-sample` |

### Customizing the System Prompt

Edit `prompts/system_prompt.txt` to customize how the agent responds to queries and interprets the database schema.

## Usage Examples

Once running, you can ask natural language questions like:

- *"Show me all airlines from the United States"*
- *"How many hotels are in France?"*
- *"What are the top 10 most popular airport destinations?"*
- *"Find flights departing from SFO tomorrow"*

The agent will:
1. Analyze your question
2. Discover relevant collections/schema if needed
3. Generate and execute a SQL++ query
4. Present the results in a readable format

## Troubleshooting

### MCP Connection Failed
- Ensure the Couchbase MCP server is running
- Verify `MCP_SERVER_URL` is correct in `.env`

### LLM Errors
- Check your Azure OpenAI credentials in `components/azure-openai.yaml`
- Verify the deployment name matches your Azure resource

### Agent Not Ready
- Refresh the page to reinitialize the connection
- Check Dapr logs: `dapr logs -a cb-agent`

## License

MIT License - See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
