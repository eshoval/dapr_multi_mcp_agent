"""
Dapr MCP AI Agent POC
A natural language chatbot using Dapr Agents + Chainlit that queries multiple DBs via MCP.
"""

import os
from pathlib import Path
from typing import Optional

import chainlit as cl
from dotenv import load_dotenv
from dapr_agents import Agent
from dapr_agents.tool.mcp.client import MCPClient
from dapr_agents.llm.dapr import DaprChatClient

load_dotenv()

# MCP Server URLs
CB_MCP_SERVER_URL = os.getenv("CB_MCP_SERVER_URL", "http://localhost:8000/sse")
PG_MCP_SERVER_URL = os.getenv("PG_MCP_SERVER_URL", "http://localhost:8003/sse")
CB_BUCKET_NAME = os.getenv("CB_BUCKET_NAME", "travel-sample")

# Global state
agent: Optional[Agent] = None
cb_mcp_client: Optional[MCPClient] = None
pg_mcp_client: Optional[MCPClient] = None


def load_system_prompt() -> str:
    """Load system prompt from prompts directory."""
    prompt_file = Path(__file__).parent / "prompts" / "system_prompt.txt"
    return prompt_file.read_text(encoding="utf-8")


async def init_agent():
    """Initialize or reset the agent with MCP connections."""
    global agent, cb_mcp_client, pg_mcp_client
    
    # Cleanup existing connections
    for client in [cb_mcp_client, pg_mcp_client]:
        if client:
            try:
                await client.close()
            except RuntimeError:
                pass
    cb_mcp_client = None
    pg_mcp_client = None
    agent = None
    
    # Connect to Couchbase MCP
    cb_mcp_client = MCPClient(persistent_connections=True)
    await cb_mcp_client.connect_sse(server_name="couchbase", url=CB_MCP_SERVER_URL)
    
    # Connect to PostgreSQL MCP 
    pg_mcp_client = MCPClient(persistent_connections=True)
    await pg_mcp_client.connect_sse(server_name="postgres", url=PG_MCP_SERVER_URL)
    
    agent = Agent(
        name="DBAgent",
        role="Database Expert",
        instructions=[load_system_prompt()],
        llm=DaprChatClient(
            component_name=os.getenv("DAPR_LLM_COMPONENT_DEFAULT", "openai"),
            provider=os.getenv("DAPR_LLM_PROVIDER_DEFAULT", "openai"),
            timeout=180
        ),
        tools=cb_mcp_client.get_all_tools() + pg_mcp_client.get_all_tools()
    )


@cl.on_chat_start
async def on_chat_start():
    """Initialize agent when chat starts."""
    try:
        await init_agent()
        pg_tools_count = len(pg_mcp_client.get_all_tools())
        cb_tools_count = len(cb_mcp_client.get_all_tools())
        await cl.Message(
            content=f"Connected to DB MCP server. Ready to query the '{CB_BUCKET_NAME}' bucket. Couchbase MCP loaded ({cb_tools_count} tools). PostgreSQL MCP loaded ({pg_tools_count} tools). Ask me anything!",
            actions=[cl.Action(name="reset_agent", payload={}, label="🔄 Reset Agent")]
        ).send()
    except Exception as e:
        await cl.Message(content=f"Failed to connect to MCP servers: {e}").send()


@cl.on_chat_end
async def on_chat_end():
    """Cleanup MCP connections when chat ends."""
    global cb_mcp_client, pg_mcp_client
    for client in [cb_mcp_client, pg_mcp_client]:
        if client:
            try:
                await client.close()
            except RuntimeError:
                pass
    cb_mcp_client = None
    pg_mcp_client = None


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming user messages."""
    if agent is None:
        await cl.Message(content="Agent not ready. Please refresh the page.").send()
        return
    
    try:
        response = await agent.run(message.content)
        await cl.Message(content=response.content or "No response generated.").send()
    except Exception as e:
        await cl.Message(content=f"Error: {e}").send()


@cl.action_callback("reset_agent")
async def on_reset_action(action: cl.Action):
    """Handle Reset button click."""
    await cl.Message(content="🔄 Resetting agent...").send()
    try:
        await init_agent()
        await cl.Message(content=f"✅ Agent reset! Ready to query '{CB_BUCKET_NAME}'.").send()
    except Exception as e:
        await cl.Message(content=f"❌ Reset failed: {e}").send()
