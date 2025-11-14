
"""
FASTQC Quality Control Agent

This agent analyzes FASTQC quality control reports and provides recommendations
for genomics data preprocessing and quality improvement.
"""

import logging
import sys
import os
import tempfile
import zipfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from strands.agent.conversation_manager import SummarizingConversationManager
from mcp import stdio_client, StdioServerParameters

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state for temporary directories
temp_dirs = []

# Use summarizing conversation manager
conversation_manager = SummarizingConversationManager(
    summary_ratio=0.4,
    preserve_recent_messages=8
)

@tool
def extract_zip_file(zip_path: str) -> Dict[str, Any]:
    """Extract a zip file to a temporary directory

    Args:
        zip_path: Path to the zip file to extract

    Returns:
        Dictionary with extraction results and temp directory path
    """
    global temp_dirs
    try:
        if not os.path.exists(zip_path):
            return {
                "success": False,
                "error": f"Zip file not found: {zip_path}",
                "temp_dir": None,
                "extracted_files": []
            }

        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix="fastqc_extract_")
        temp_dirs.append(temp_dir)

        # Extract zip file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # List extracted files
        extracted_files = []
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, temp_dir)
                extracted_files.append({
                    "name": file,
                    "path": file_path,
                    "relative_path": relative_path,
                    "size": os.path.getsize(file_path)
                })

        logger.info(f"Extracted {len(extracted_files)} files to {temp_dir}")

        return {
            "success": True,
            "temp_dir": temp_dir,
            "extracted_files": extracted_files,
            "file_count": len(extracted_files)
        }

    except Exception as e:
        logger.error(f"Error extracting zip file: {e}")
        return {
            "success": False,
            "error": str(e),
            "temp_dir": None,
            "extracted_files": []
        }

@tool
def read_file_contents(file_path: str, max_lines: int = 1000) -> Dict[str, Any]:
    """Read contents of a text file

    Args:
        file_path: Path to the file to read
        max_lines: Maximum number of lines to read (default: 1000)

    Returns:
        Dictionary with file contents and metadata
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "content": "",
                "lines": []
            }

        # Read file contents
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line.rstrip('\n\r'))

        content = '\n'.join(lines)

        logger.info(f"Read {len(lines)} lines from {file_path}")

        return {
            "success": True,
            "content": content,
            "lines": lines,
            "line_count": len(lines),
            "file_path": file_path,
            "truncated": len(lines) >= max_lines
        }

    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return {
            "success": False,
            "error": str(e),
            "content": "",
            "lines": []
        }

def create_qc_agent(mcp_tools):
    """Create the FASTQC quality control agent"""

    # Configure the model provider (using Amazon Bedrock with default Claude model)
    model = BedrockModel(
        # model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",  # inference profile ID
        # model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0",
        model_id="global.anthropic.claude-sonnet-4-20250514-v1:0",
        temperature=0.0,  # lower temperature for more focused responses
        max_tokens=4096
        #cache_prompt="default",  # Cache system prompt
        #cache_tools="default"     # Cache tool definitions
    )

    # Combine MCP tools with custom tools
    all_tools = mcp_tools + [extract_zip_file, read_file_contents]

    # Create the agent
    agent = Agent(
        name="FASTQC Quality Control Agent",
        model=model,
        tools=all_tools,
        conversation_manager=conversation_manager
    )

    return agent
