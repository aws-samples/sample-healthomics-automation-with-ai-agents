
"""
This agent is responsible for finding genomics data files (FASTQ pairs) for a given sample ID. 
It will then pass the URIs of the FASTQ pairs to the quality control agent."""

import logging
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from strands.agent.conversation_manager import SummarizingConversationManager

from mcp import stdio_client, StdioServerParameters

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use summarizing conversation manager
conversation_manager = SummarizingConversationManager(
    summary_ratio=0.4,
    preserve_recent_messages=8
)

def create_data_discovery_agent(mcp_tools):
    """Create the HealthOmics data discovery agent"""

    # Configure the model provider (using Amazon Bedrock with default Claude model)
    model = BedrockModel(
        # model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",  # inference profile ID
        # model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0",
        model_id="global.anthropic.claude-sonnet-4-20250514-v1:0",
        temperature=0.0,  # lower temperature for more focused responses
        max_tokens=4096
        #cache_prompt="default",  # Cache system prompt
        #cache_tools="default",     # Cache tool definitions
    )

    # Create the agent
    agent = Agent(
        name="HealthOmics Data Discovery Agent",
        model=model,
        tools=mcp_tools,
        conversation_manager=conversation_manager
    )

    return agent
