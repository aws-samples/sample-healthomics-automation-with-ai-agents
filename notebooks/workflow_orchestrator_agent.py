
"""Workflow Orchestrator Agent:
   This agent is responsible for orchestrating the genomics variant calling workflow when data quality is sufficient.
   It will monitor the workflow run status until completion.
"""

import asyncio
import logging
import time
import os
import boto3
from botocore.exceptions import ClientError
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from strands.agent.conversation_manager import SummarizingConversationManager
from mcp import stdio_client, StdioServerParameters

# Import file tools if available (optional dependency)
try:
    from strands_tools import file_read, file_write, editor
    FILE_TOOLS_AVAILABLE = True
except ImportError:
    FILE_TOOLS_AVAILABLE = False
    file_read = file_write = editor = None

# Bypass tool consent for automated workflows
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use summarizing conversation manager
conversation_manager = SummarizingConversationManager(
    summary_ratio=0.4,
    preserve_recent_messages=8
)

@tool
async def wait_for_workflow(run_id: str, max_wait_minutes: int = 60, poll_interval_seconds: int = 30) -> str:
    """
    Wait for a HealthOmics workflow run to complete by polling the run status.
    Checks the run status at regular intervals and returns early when the run reaches a terminal state.

    Args:
        run_id: The HealthOmics run ID to monitor
        max_wait_minutes: Maximum time to wait in minutes (default: 60, max: 120 for safety)
        poll_interval_seconds: Seconds between status checks (default: 30, min: 10, max: 300)

    Returns:
        str: Status message indicating the final run state and duration
    """
    # Limit maximum wait time for safety
    max_wait_minutes = min(max(max_wait_minutes, 1), 120)  # Between 1 and 120 minutes
    max_wait_seconds = max_wait_minutes * 60
    
    # Validate and constrain poll interval
    poll_interval_seconds = min(max(poll_interval_seconds, 10), 300)  # Between 10s and 5min

    logger.info(f"Monitoring HealthOmics run {run_id} (max wait: {max_wait_minutes} minutes, poll interval: {poll_interval_seconds}s)...")

    # Initialize HealthOmics client
    try:
        omics_client = boto3.client('omics')
    except Exception as e:
        return f"Error initializing HealthOmics client: {str(e)}"

    # Terminal states that indicate the run is complete
    terminal_states = {'COMPLETED', 'FAILED', 'CANCELLED', 'DELETED'}

    chunks = max_wait_seconds // poll_interval_seconds
    start_time = time.time()

    for i in range(chunks):
        try:
            # Check run status using HealthOmics GetRun API
            response = omics_client.get_run(id=run_id)
            current_status = response.get('status', 'UNKNOWN')

            elapsed_minutes = ((i + 1) * poll_interval_seconds) / 60
            logger.info(f"Run {run_id} status: {current_status} (elapsed: {elapsed_minutes:.1f}/{max_wait_minutes} minutes)")

            # Check if run has reached a terminal state
            if current_status in terminal_states:
                total_elapsed = time.time() - start_time
                elapsed_minutes = total_elapsed / 60

                if current_status == 'COMPLETED':
                    logger.info(f"Run {run_id} completed successfully after {elapsed_minutes:.1f} minutes")
                    return f"HealthOmics run {run_id} completed successfully after {elapsed_minutes:.1f} minutes. Status: {current_status}"
                elif current_status == 'FAILED':
                    failure_reason = response.get('failureReason', 'Unknown failure reason')
                    logger.error(f"Run {run_id} failed after {elapsed_minutes:.1f} minutes: {failure_reason}")
                    return f"HealthOmics run {run_id} failed after {elapsed_minutes:.1f} minutes. Status: {current_status}. Reason: {failure_reason}"
                elif current_status == 'CANCELLED':
                    logger.info(f"Run {run_id} was cancelled after {elapsed_minutes:.1f} minutes")
                    return f"HealthOmics run {run_id} was cancelled after {elapsed_minutes:.1f} minutes. Status: {current_status}"
                else:  # DELETED
                    logger.info(f"Run {run_id} was deleted after {elapsed_minutes:.1f} minutes")
                    return f"HealthOmics run {run_id} was deleted after {elapsed_minutes:.1f} minutes. Status: {current_status}"

            # Wait for the next check interval (configurable polling)
            await asyncio.sleep(poll_interval_seconds)

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))

            if error_code == 'ResourceNotFoundException':
                return f"HealthOmics run {run_id} not found. It may have been deleted or the ID is incorrect."
            elif error_code in ['AccessDeniedException', 'UnauthorizedOperation']:
                return f"Access denied when checking run {run_id}. Please verify IAM permissions for HealthOmics GetRun operation."
            else:
                logger.warning(f"Error checking run status (attempt {i+1}): {error_code} - {error_message}")
                # Continue trying for transient errors
                await asyncio.sleep(poll_interval_seconds)

        except Exception as e:
            logger.warning(f"Unexpected error checking run status (attempt {i+1}): {str(e)}")
            # Continue trying for unexpected errors
            await asyncio.sleep(poll_interval_seconds)

    # If we've reached the maximum wait time without a terminal state
    total_elapsed = time.time() - start_time
    elapsed_minutes = total_elapsed / 60

    try:
        # Get final status
        response = omics_client.get_run(id=run_id)
        final_status = response.get('status', 'UNKNOWN')
        logger.warning(f"Maximum wait time reached. Run {run_id} status: {final_status} after {elapsed_minutes:.1f} minutes")
        return f"""Maximum wait time ({max_wait_minutes} minutes) reached. HealthOmics run {run_id} is still running with status: {final_status}. Consider checking the run status manually or increasing the wait time."""
    except Exception as e:
        logger.error(f"Failed to get final run status: {str(e)}")
        return f"Maximum wait time ({max_wait_minutes} minutes) reached for run {run_id}. Unable to determine final status due to error: {str(e)}"


def create_healthomics_agent(mcp_tools):
    """Create the HealthOmics workflow orchestrator agent"""

    # Configure the model provider (using Amazon Bedrock with default Claude model)
    model = BedrockModel(
        model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0", # inference profile ID
        # model_id="global.anthropic.claude-sonnet-4-20250514-v1:0",
        temperature=0.0, # lower temperature for more focussed responses
        max_tokens=4096
    )

    # Combine MCP tools with built-in tools
    all_tools = mcp_tools + [wait_for_workflow] if mcp_tools else [wait_for_workflow]

    # Add Strands built in file tools if available
    if FILE_TOOLS_AVAILABLE:
        all_tools += [file_read, file_write, editor]


    session = boto3.Session()
    region = session.region_name
    print(f"The current AWS region is: {region}")  

    # Create the agent
    agent = Agent(
        name="HealthOmics Workflow Orchestrator",
        description="""
            I'm your AWS HealthOmics workflow orchestrator. I can help you:
            
            - Generate workflows
            - Read, Write and Edit workflow definitions from and to files
            - Create and manage HealthOmics workflows
            - Start and monitor workflow runs with real-time status monitoring
            - Analyze workflow performance and optimize resource usage
            - Troubleshoot failed workflows
            - Lint and validate workflow definitions (WDL/CWL)
            - Package workflows for deployment
            
            I have access to comprehensive HealthOmics APIs and can guide you through
            genomics workflow management on AWS.
            """,
        model=model,
        tools=all_tools,
        conversation_manager=conversation_manager,
        system_prompt=f"""
            You are an expert AWS HealthOmics workflow orchestrator agent. Your role is to:
            
            1. Help users create, deploy, and manage HealthOmics workflows
            2. Monitor workflow execution and provide real-time status updates
            3. Analyze workflow performance and suggest optimizations
            4. Troubleshoot workflow failures with detailed diagnostics
            5. Validate workflow definitions and ensure best practices
            
            Always provide clear, actionable guidance and use your available tools
            to perform operations. Be proactive in suggesting optimizations and best practices.

            When creating workflows, follow these guidelines:
            1. Unless otherwise instructed, create workflows in WDL 1.1
            2. Ensure all tasks have suitable cpu, memory and container directives
            3. Favoring use of containers from quay.io such as biocontianers for bioinformatics tasks or quay.io/lib/debian for general tasks
            4. Use the LintAHOWorkflowDefinition or LintAHOWorkflowBundle tools to ensure correctness
            5. Use the container registry map URI s3://aws-genomics-static-{region}/omics-data/tumor-normal/healthomics_configs/container_registry_map_quay.json
            6. Use DYNAMIC storage as the storage type for workflows
            7. When possible and logical, scatter over inputs or genomic intervals to improve computational efficiency
            8. When creating updates to existing workflows, create workflow versions rather than new workflows
            9. Use `set -euo pipefail` in task commands
            10. `echo` the names and values of task inputs in the task command to assist with debugging
            
            When updating a workflow:
            1. Create a new version of the workflow you are updating
            2. Use semantic versioning for the version name

            When running a workflow:
            1. Always run the most recent version of the workflow
            2. Use an IAM role with a trust policy for the `omics` principal that has appropriate permissions to read inputs
               and write outputs
            3. Set the workflow output location to an s3 folder that the IAM role has access to   

            IMPORTANT: When you start a workflow run, you will receive a run ID. Use the wait_for_workflow tool 
            with this run ID to monitor the run status until completion. This tool polls the HealthOmics API 
            every 30 seconds and returns early when the run reaches a terminal state.
            """
    )

    return agent
