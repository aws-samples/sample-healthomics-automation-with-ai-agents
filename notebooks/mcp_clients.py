
import sys
import boto3
import logging

from strands.tools.mcp import MCPClient
from strands.multiagent import GraphBuilder
from strands.multiagent.graph import Graph
from mcp import stdio_client, StdioServerParameters

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_genomics_search_config():
    """Get genomics search configuration for MCP servers."""

    session = boto3.Session()
    region = session.region_name
    print(f"The current AWS region is: {region}")

    return {
        "FASTMCP_LOG_LEVEL": "ERROR",
        "GENOMICS_SEARCH_S3_BUCKETS": f"s3://aws-genomics-static-{region}/omics-data/",
        "GENOMICS_SEARCH_ENABLE_S3_TAG_SEARCH": "true",
        "GENOMICS_SEARCH_MAX_TAG_BATCH_SIZE": "100", 
        "GENOMICS_SEARCH_RESULT_CACHE_TTL": "600",
        "GENOMICS_SEARCH_TAG_CACHE_TTL": "300",
        "GENOMICS_SEARCH_MAX_CONCURRENT": "10",
        "GENOMICS_SEARCH_TIMEOUT_SECONDS": "300",
        "GENOMICS_SEARCH_ENABLE_HEALTHOMICS": "true"
    }


def setup_mcp_clients():
    """Set up MCP clients for the multi-agent system"""
    try:
        # Get genomics search configuration
        genomics_config = get_genomics_search_config()

        # Create MCP clients for different services
        healthomics_client = MCPClient(
            lambda: stdio_client(StdioServerParameters(
                command="uvx",
                args=["awslabs.aws-healthomics-mcp-server@latest"],
                env=genomics_config
            ))
        )

        # AWS API MCP server for QC operations
        aws_api_client = MCPClient(
            lambda: stdio_client(StdioServerParameters(
                command="uvx", 
                args=["awslabs.aws-api-mcp-server@latest"],
            ))
        )

        print("🔌 MCP clients created successfully")
        return healthomics_client, aws_api_client

    except Exception as e:
        logger.error(f"Failed to set up MCP servers: {e}")
        sys.exit(1)
