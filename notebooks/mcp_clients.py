
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
    return {
        "FASTMCP_LOG_LEVEL": "ERROR",
        "GENOMICS_SEARCH_S3_BUCKETS": "s3://aws-genomics-static-us-east-1/omics-data/",
        "GENOMICS_SEARCH_ENABLE_S3_TAG_SEARCH": "true",
        "GENOMICS_SEARCH_MAX_TAG_BATCH_SIZE": "100", 
        "GENOMICS_SEARCH_RESULT_CACHE_TTL": "600",
        "GENOMICS_SEARCH_TAG_CACHE_TTL": "300",
        "GENOMICS_SEARCH_MAX_CONCURRENT": "10",
        "GENOMICS_SEARCH_TIMEOUT_SECONDS": "300",
        "GENOMICS_SEARCH_ENABLE_HEALTHOMICS": "true"
    }

def get_credentials():
    session = boto3.Session()
    credentials = session.get_credentials()

    # Prepare environment variables with AWS credentials
    # This is only required in notebooks where the host metadata endpoint is blocked
    env_vars = {
        "AWS_REGION": session.region_name or 'us-east-1',
    }

    if credentials:
        env_vars.update({
            "AWS_ACCESS_KEY_ID": credentials.access_key,
            "AWS_SECRET_ACCESS_KEY": credentials.secret_key,
        })
        if credentials.token:
            env_vars["AWS_SESSION_TOKEN"] = credentials.token

    return env_vars


def setup_mcp_clients():
    """Set up MCP clients for the multi-agent system"""
    try:
        # Get genomics search configuration
        genomics_config = get_genomics_search_config()
        creds = get_credentials()

        # merge the two dictionaries
        env_vars = genomics_config | creds

        # Create MCP clients for different services
        healthomics_client = MCPClient(
            lambda: stdio_client(StdioServerParameters(
                command="uvx",
                args=["awslabs.aws-healthomics-mcp-server@latest"],
                env=env_vars
            ))
        )

        # AWS API MCP server for QC operations
        aws_api_client = MCPClient(
            lambda: stdio_client(StdioServerParameters(
                command="uvx", 
                args=["awslabs.aws-api-mcp-server@latest"],
                env=creds
            ))
        )

        print("🔌 MCP clients created successfully")
        return healthomics_client, aws_api_client

    except Exception as e:
        logger.error(f"Failed to set up MCP servers: {e}")
        sys.exit(1)
