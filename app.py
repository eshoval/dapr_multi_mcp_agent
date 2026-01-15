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

# MCP Server Configuration
CB_MCP_SERVER_URL = os.getenv("CB_MCP_SERVER_URL", "http://localhost:8000/sse")
PG_MCP_SERVER_URL = os.getenv("PG_MCP_SERVER_URL", "http://localhost:8003/sse")
CB_MCP_ACTIVE = os.getenv("CB_MCP_ACTIVE", "true").lower() == "true"
PG_MCP_ACTIVE = os.getenv("PG_MCP_ACTIVE", "true").lower() == "true"
CB_BUCKET_NAME = os.getenv("CB_BUCKET_NAME", "travel-sample")

# Global state
agent: Optional[Agent] = None
cb_mcp_client: Optional[MCPClient] = None
pg_mcp_client: Optional[MCPClient] = None


def load_system_prompt() -> str:
    """Load system prompt, adding DB-specific prompts if active."""
    prompts_dir = Path(__file__).parent / "prompts"
    
    # Base system prompt
    prompt = (prompts_dir / "system_prompt.txt").read_text(encoding="utf-8")
    
    # Add Couchbase-specific prompt if active
    if CB_MCP_ACTIVE:
        cb_prompt_file = prompts_dir / "couchbase_prompt.txt"
        if cb_prompt_file.exists():
            prompt += "\n\n" + cb_prompt_file.read_text(encoding="utf-8")
    
    return prompt


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
    
    # Connect to Couchbase MCP if active
    if CB_MCP_ACTIVE:
        cb_mcp_client = MCPClient(persistent_connections=True)
        await cb_mcp_client.connect_sse(server_name="couchbase", url=CB_MCP_SERVER_URL)
    
    # Connect to PostgreSQL MCP if active
    if PG_MCP_ACTIVE:
        pg_mcp_client = MCPClient(persistent_connections=True)
        await pg_mcp_client.connect_sse(server_name="postgres", url=PG_MCP_SERVER_URL)
    
    # Check if at least one DB is available
    if not CB_MCP_ACTIVE and not PG_MCP_ACTIVE:
        raise RuntimeError("No DB available - both CB_MCP_ACTIVE and PG_MCP_ACTIVE are false")
    
    # Collect tools from active MCP clients
    all_tools = []
    if cb_mcp_client:
        all_tools.extend(cb_mcp_client.get_all_tools())
    if pg_mcp_client:
        all_tools.extend(pg_mcp_client.get_all_tools())
    
    agent = Agent(
        name="DBAgent",
        role="Database Expert",
        instructions=[load_system_prompt()],
        llm=DaprChatClient(
            component_name=os.getenv("DAPR_LLM_COMPONENT_DEFAULT", "openai"),
            provider=os.getenv("DAPR_LLM_PROVIDER", "openai"),
            timeout=180
        ),
        tools=all_tools
    )


@cl.on_chat_start
async def on_chat_start():
    """Initialize agent when chat starts."""
    try:
        await init_agent()
        
        # Build status message based on active DBs
        status_parts = []
        if cb_mcp_client:
            cb_tools_count = len(cb_mcp_client.get_all_tools())
            status_parts.append(f"Couchbase MCP ({cb_tools_count} tools)")
        if pg_mcp_client:
            pg_tools_count = len(pg_mcp_client.get_all_tools())
            status_parts.append(f"PostgreSQL MCP ({pg_tools_count} tools)")
        
        await cl.Message(
            content=f"Connected to: {', '.join(status_parts)}. Ask me anything!",
            actions=[
                cl.Action(name="reset_agent", payload={}, label="🔄 Reset Agent"),
                cl.Action(name="reload_env", payload={}, label="📥 Reload Env"),
                cl.Action(name="exit_app", payload={}, label="🚪 Exit App")
            ]
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


@cl.action_callback("reload_env")
async def on_reload_env_action(action: cl.Action):
    """Handle Reload Env button click - reload .env and reinitialize agent."""
    global CB_MCP_SERVER_URL, PG_MCP_SERVER_URL, CB_MCP_ACTIVE, PG_MCP_ACTIVE, CB_BUCKET_NAME
    
    await cl.Message(content="📥 Reloading environment...").send()
    
    try:
        # Reload .env file (override=True to update existing values)
        load_dotenv(override=True)
        
        # Update global config variables
        CB_MCP_SERVER_URL = os.getenv("CB_MCP_SERVER_URL", "http://localhost:8000/sse")
        PG_MCP_SERVER_URL = os.getenv("PG_MCP_SERVER_URL", "http://localhost:8003/sse")
        CB_MCP_ACTIVE = os.getenv("CB_MCP_ACTIVE", "true").lower() == "true"
        PG_MCP_ACTIVE = os.getenv("PG_MCP_ACTIVE", "true").lower() == "true"
        CB_BUCKET_NAME = os.getenv("CB_BUCKET_NAME", "travel-sample")
        
        # Reinitialize agent with new config
        await init_agent()
        
        await cl.Message(content=f"✅ Environment reloaded! CB_ACTIVE={CB_MCP_ACTIVE}, PG_ACTIVE={PG_MCP_ACTIVE}").send()
    except Exception as e:
        await cl.Message(content=f"❌ Reload failed: {e}").send()


@cl.action_callback("exit_app")
async def on_exit_action(action: cl.Action):
    """Handle Exit button click - shutdown the app."""
    import os as _os
    
    await cl.Message(content="🚪 Shutting down application...").send()
    
    # Use os._exit() for immediate termination
    # MCP cleanup is skipped as it fails across async task contexts
    _os._exit(0)
