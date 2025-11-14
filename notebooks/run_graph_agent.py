#!/usr/bin/env python3
"""
Standalone script to run the genomics multi-agent graph locally.
Usage: python run_graph_agent.py "Your prompt here"
"""

import sys
import asyncio
import logging
from graph_agent import get_or_create_graph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_graph_with_prompt(prompt: str):
    """Run the graph agent with a user prompt and stream results"""
    logger.info(f"🚀 Starting genomics multi-agent graph with prompt: {prompt}")
    
    try:
        # Get or create the graph (initializes MCP clients on first call)
        graph = get_or_create_graph()
        logger.info("✅ Graph initialized successfully")
        logger.info(f"Graph type: {type(graph)}")
        logger.info(f"Graph methods: {[m for m in dir(graph) if not m.startswith('_')]}")
        
        # Execute the graph
        print("\n" + "="*80)
        print("GRAPH AGENT RESPONSE")
        print("="*80 + "\n")
        
        # Execute the graph (Graph uses invoke_async, not stream_async)
        result = await graph.invoke_async(prompt)
        
        # Display results from each node
        print("\n" + "="*80)
        print("EXECUTION SUMMARY")
        print("="*80)
        print(f"\nStatus: {result.status}")
        print(f"Total Nodes: {result.total_nodes}")
        print(f"Completed Nodes: {result.completed_nodes}")
        print(f"Failed Nodes: {result.failed_nodes}")
        print(f"Execution Time: {result.execution_time}ms")
        
        print("\n" + "-"*80)
        print("NODE RESULTS")
        print("-"*80)
        
        for node_id, node_result in result.results.items():
            print(f"\n🔹 {node_id}:")
            print(f"   Status: {node_result.status}")
            print(f"   Execution Time: {node_result.execution_time}ms")
            if node_result.result:
                result_text = str(node_result.result)
                # Truncate long results
                if len(result_text) > 500:
                    print(f"   Result: {result_text[:500]}...")
                else:
                    print(f"   Result: {result_text}")
        
        print("\n" + "="*80)
        print("GRAPH EXECUTION COMPLETED")
        print("="*80 + "\n")
        
    except Exception as e:
        logger.error(f"❌ Error running graph: {str(e)}", exc_info=True)
        print(f"\n❌ Error: {str(e)}\n")
        sys.exit(1)


def main():
    """Main entry point for the script"""
    if len(sys.argv) < 2:
        print("Usage: python run_graph_agent.py \"Your prompt here\"")
        print("\nExample:")
        print('  python run_graph_agent.py "Find and analyze genomics data for sample P001"')
        sys.exit(1)
    
    # Get the prompt from command line arguments
    prompt = " ".join(sys.argv[1:])
    
    # Run the async function
    asyncio.run(run_graph_with_prompt(prompt))


if __name__ == "__main__":
    main()
