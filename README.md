# 🧬 AI for Genomics Automation Workshop 

A comprehensive workshop demonstrating AI-driven genomics workflow automation using AWS HealthOmics, Strands Agents, and multi-agent systems.

## 🎯 Overview

This workshop teaches you to build intelligent AI agents that can automate genomics workflows on AWS HealthOmics. You'll learn to create agents that can manage workflows, monitor runs, analyze results, and troubleshoot issues autonomously.

## 🏗️ Architecture

- **Strands Agents Framework** - Python framework for building AI agents
- **AWS HealthOmics** - Managed genomics service for workflow execution
- **Model Context Protocol (MCP)** - Tool connectivity for external systems
- **Multi-Agent Systems** - Coordinated agents for complex genomics pipelines

## 📚 Workshop Structure

### 1. Introduction to Strands Agents (`01-strands-agents-introduction.ipynb`)
- Core concepts and architecture
- Building your first HealthOmics agent
- MCP integration and tool connectivity
- Interactive experimentation

### 2. Genomics Supervisor Agent (`02-genomics-supervisor-agent.ipynb`)
- Advanced agent orchestration
- Workflow management and monitoring
- Performance optimization strategies

### 3. Multi-Agent Genomics Pipeline (`03-multi-agent-genomics-pipeline.ipynb`)
- Coordinated multi-agent systems
- Specialized agents for different pipeline stages
- End-to-end automation workflows

## 🛠️ Prerequisites

- AWS Account with HealthOmics access
- Python 3.12+
- Basic understanding of genomics workflows
- Familiarity with WDL/CWL workflow languages

## 🚀 Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd sample-healthomics-automation-with-ai-agents
   ```

2. **Install dependencies**
   ```bash
   pip install -r notebooks/requirements.txt
   ```
3. **Build workflow**
   ```bash
   cd somatic_variant_calling 
   zip mutect2.zip main.wdl
   aws s3 cp mutect2.zip s3://<your-bucket>/<your-prefix>/mutect2.zip
   ```
4. **Deploy infrastructure**
   ```bash
   aws cloudformation deploy \
     --template-file infrastructure/infrastructure_cfn.yaml \
     --stack-name genomics-ai-workshop \
     --capabilities CAPABILITY_NAMED_IAM \
     --parameter-overrides \
       OmicsResourcesS3Bucket=<your-bucket> \
       OmicsResourcesS3Prefix=<your-prefix> \
       OmicsWorkflowDefinitionZipS3=mutect2.zip
   ```

5. **Start the workshop**
   - Open `notebooks/01-strands-agents-introduction.ipynb`
   - Follow the step-by-step instructions

## 📁 Project Structure

```
├── notebooks/                          # Interactive Jupyter notebooks
│   ├── 01-strands-agents-introduction.ipynb
│   ├── 02-genomics-supervisor-agent.ipynb
│   ├── 03-multi-agent-genomics-pipeline.ipynb
│   ├── civic-data/                     # Sample genomics data
│   │   ├── AssertionSummaries.tsv
│   │   ├── ClinicalEvidenceSummaries.tsv
│   │   ├── FeatureSummaries.tsv
│   │   └── VariantSummaries.tsv
│   ├── data_discovery_agent.py         # Data discovery agent implementation
│   ├── interpretation_and_reporting_agent.py # Reporting agent
│   ├── mcp_clients.py                  # MCP client configurations
│   ├── qc_agent.py                     # Quality control agent
│   ├── run_graph_agent.py              # Run monitoring agent
│   ├── workflow_orchestrator_agent.py  # Workflow orchestration agent
│   ├── test_workflow_orchestrator.py   # Test utilities
│   └── requirements.txt                # Python dependencies
├── infrastructure/                     # AWS CloudFormation templates
│   ├── infrastructure_cfn.yaml        # Main infrastructure
│   └── start_workflow/                # Lambda functions
│       ├── start_workflow_lambda.py   # Workflow starter Lambda
│       ├── build.sh                   # Build script
dependencies
├── somatic-variant-calling-pipeline/   # Sample WDL workflow
│   ├── main.wdl                       # Mutect2 workflow
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

## 🤖 Agent Capabilities

### Core Agents
- **Data Discovery Agent** - Find and catalog genomics datasets
- **QC Agent** - Quality control and validation
- **Workflow Orchestrator** - Manage workflow execution
- **Interpretation & Reporting** - Analyze results and generate reports

### Key Features
- **Workflow Management** - Create, deploy, and version workflows
- **Real-time Monitoring** - Track execution with automatic polling
- **Performance Analysis** - Resource optimization recommendations
- **Failure Diagnostics** - Automated troubleshooting
- **Validation** - WDL/CWL syntax checking and best practices

## 🔧 Infrastructure Components

- **HealthOmics Workflows** - Pre-configured Mutect2 somatic variant calling
- **HealthOmics Workflow Run** -- Run a test Mutect2 workflow with publicly available data
- **S3 Storage** - Workflow results and genomics data
- **IAM Roles** - Secure access management
- **SageMaker Notebook** - Interactive development environment
- **ECR Repositories** - Container image management

## 📊 Sample Workflows

### Mutect2 Somatic Variant Calling
- Tumor/normal pair analysis
- Scatter-gather parallelization
- VCF to MAF conversion
- Configurable "cooking show" mode for demonstrations

## 🎓 Learning Outcomes

By completing this workshop, you will:

1. **Build Production AI Agents** - Create robust agents using Strands framework
2. **Integrate MCP Tools** - Connect agents to external systems seamlessly
3. **Automate Genomics Workflows** - End-to-end pipeline automation
4. **Implement Multi-Agent Systems** - Coordinate specialized agents
5. **Optimize Performance** - Resource usage and cost optimization
6. **Handle Failures** - Automated error detection and recovery

## 🔍 Key Technologies

- **Strands Agents** - AI agent framework
- **AWS HealthOmics** - Genomics workflow service
- **Amazon Bedrock** - Foundation models (Claude)
- **Model Context Protocol** - Tool integration standard
- **WDL** - Workflow description languages
- **GATK** - Genomics analysis toolkit

## 📝 Requirements

```
strands-agents>=1.0.0
boto3
pandas>=2.3.0
bedrock-agentcore
awslabs-aws-healthomics-mcp-server
awslabs.aws-api-mcp-server>=0.0.13
uv
```


## 🆘 Support

For workshop-related questions:
- Check the notebook documentation
- Review the infrastructure logs
- Consult AWS HealthOmics documentation


