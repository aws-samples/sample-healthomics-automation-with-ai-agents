#!/usr/bin/env python3
"""
Simple test script to demonstrate creating and using the HealthOmics workflow orchestrator agent.
"""

import asyncio
from workflow_orchestrator_agent import create_healthomics_agent
from mcp_clients import setup_mcp_clients

async def main():
    """Test the workflow orchestrator agent creation and basic interaction."""
    
    print("🚀 Setting up MCP clients...")
    healthomics_client, aws_api_client = setup_mcp_clients()
    
    print("\n🤖 Creating HealthOmics workflow orchestrator agent...")
    
    # Use manual context management to get tools
    with healthomics_client:
        mcp_tools = healthomics_client.list_tools_sync()
        print(f"✅ Loaded {len(mcp_tools)} MCP tools")
        
        # Create the agent
        agent = create_healthomics_agent(mcp_tools)
        print(f"✅ Agent created: {agent.name}")
        print(f"   Description: {agent.description.strip()[:100]}...")
        
        # Test a simple interaction
        print("\n💬 Testing agent interaction...")
        response = agent("What can you help me with?")
        print(f"\n🤖 Agent response:\n{response.message['content'][0]['text']}")
        
        print("\n✅ Test completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
