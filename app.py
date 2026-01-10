"""
Dapr MCP-Couchbase AI Agent POC
A natural language chatbot using Dapr Agents + Chainlit that queries Couchbase via MCP.
"""

import os
from pathlib import Path
from typing import Optional

import chainlit as cl
from dotenv import load_dotenv
from dapr_agents import Agent
from dapr_agents.tool.mcp.client import MCPClient
from dapr_agents.llm.dapr import DaprChatClient

# Load environment variables
load_dotenv()

# Configuration from .env
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/sse")
CB_BUCKET_NAME = os.getenv("CB_BUCKET_NAME", "travel-sample")

# Global state
agent: Optional[Agent] = None
mcp_client: Optional[MCPClient] = None


def load_system_prompt() -> str:
    """Load system prompt from prompts directory, create if missing."""
    prompts_dir = Path(__file__).parent / "prompts"
    prompt_file = prompts_dir / "system_prompt.txt"
    return prompt_file.read_text(encoding="utf-8") 

async def connect_mcp() -> tuple[MCPClient, list]:
    """Connect to MCP server and retrieve available tools."""
    client = MCPClient(persistent_connections=True)
    await client.connect_sse(
        server_name="couchbase",
        url=MCP_SERVER_URL,
    )
    tools = client.get_all_tools()
    return client, tools


@cl.on_chat_start
async def on_chat_start():
    """Initialize agent and MCP connection when chat starts."""
    global agent, mcp_client
    
    # Load system prompt
    system_prompt = load_system_prompt()
    
    # Connect to MCP server and get tools
    try:
        mcp_client, tools = await connect_mcp()
    except Exception as e:
        await cl.Message(content=f"Failed to connect to MCP server: {e}").send()
        return
    component_name = os.getenv("DAPR_LLM_COMPONENT_DEFAULT", "openai")
    provider = os.getenv("DAPR_LLM_PROVIDER_DEFAULT", "openai")
    
    # Create Dapr Agent with MCP tools and conversation memory
    agent = Agent(
        name="CouchbaseAgent",
        role="Database Expert",
        instructions=[system_prompt],
        llm=DaprChatClient(component_name=component_name, provider=provider, timeout=180),
        tools=tools,        
    )    
    await cl.Message(
        content=f"Connected to Couchbase MCP server. Ready to query the '{CB_BUCKET_NAME}' bucket. Ask me anything!"
    ).send()


@cl.on_chat_end
async def on_chat_end():
    """Cleanup MCP connection when chat ends."""
    global mcp_client
    if mcp_client:
        try:
            await mcp_client.close()
        except RuntimeError:
            pass  # Best-effort cleanup
        finally:
            mcp_client = None


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming user messages."""
    global agent
    
    if agent is None:
        await cl.Message(
            content="Agent is not ready. Please refresh the page to reconnect."
        ).send()
        return
    
    # Run the agent with user's question
    try:
        response = await agent.run(message.content)
        await cl.Message(content=response.content or "No response generated.").send()
    except Exception as e:
        await cl.Message(content=f"Error processing request: {e}").send()
