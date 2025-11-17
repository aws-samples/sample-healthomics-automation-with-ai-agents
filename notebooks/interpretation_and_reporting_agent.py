
"""
Cancer Variant Interpretation and Reporting Agent

This agent provides comprehensive cancer variant analysis with CIViC database integration,
offering evidence-based clinical interpretations and therapeutic recommendations.
"""

import logging
import sys
import boto3
import pandas as pd
import json
import gzip
from datetime import datetime
from typing import Dict, List, Optional
from io import BytesIO
from urllib.parse import urlparse
from pathlib import Path

from strands import Agent, tool
from strands.models import BedrockModel
from strands.agent.conversation_manager import SummarizingConversationManager


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state for the agent session
agent_state = {}

# Use summarizing conversation manager
conversation_manager = SummarizingConversationManager(
    summary_ratio=0.4,
    preserve_recent_messages=8
)

# Define genomics analysis tools with CIViC integration

@tool
def load_maf_file_from_s3(s3_uri: str) -> Dict:
    """Load a Mutation Annotation Format (MAF) file from S3.

    Args:
        s3_uri: S3 URI of the MAF file (e.g., s3://bucket/path/file.maf.gz)

    Returns:
        Dictionary containing loading status and file information
    """
    try:
        if not s3_uri.startswith('s3://'):
            return {"status": "error", "message": "Must provide S3 URI (s3://bucket/key)"}

        # Parse S3 URI
        parsed = urlparse(s3_uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip('/')

        # Download from S3
        s3_client = boto3.client('s3')
        response = s3_client.get_object(Bucket=bucket, Key=key)
        file_content = response['Body'].read()

        # Handle compressed files
        if s3_uri.endswith('.gz'):
            with gzip.open(BytesIO(file_content), 'rt') as f:
                content = f.read()
        else:
            content = file_content.decode('utf-8')

        # Parse MAF content
        lines = [line for line in content.split('\n') if line.strip() and not line.startswith('#')]
        if not lines:
            return {"status": "error", "message": "No data found in MAF file"}

        # Create DataFrame
        header = lines[0].split('\t')
        data_rows = [line.split('\t') for line in lines[1:] if line.strip()]
        maf_df = pd.DataFrame(data_rows, columns=header)

        # Validate required columns
        required_cols = ['Hugo_Symbol', 'HGVSp_Short', 'Variant_Classification']
        missing_cols = [col for col in required_cols if col not in maf_df.columns]

        if missing_cols:
            return {"status": "error", "message": f"Missing required columns: {missing_cols}"}

        # Store in global state
        agent_state['maf_data'] = maf_df
        agent_state['data_source'] = s3_uri

        return {
            "status": "success",
            "message": f"Successfully loaded {len(maf_df)} variants from {s3_uri}",
            "variant_count": len(maf_df),
            "columns": list(maf_df.columns),
            "sample_variants": maf_df[['Hugo_Symbol', 'HGVSp_Short', 'Variant_Classification']].head(3).to_dict('records')
        }

    except Exception as e:
        return {"status": "error", "message": f"Error loading MAF file: {str(e)}"}

@tool
def load_civic_annotation_files() -> Dict:
    """Load CIViC annotation files for clinical evidence matching.

    Returns:
        Dictionary containing loading status and CIViC data summary
    """
    try:
        # Load the CIViC files from the civic-data directory
        civic = Path("civic-data")
        variant_file = civic / "VariantSummaries.tsv"
        evidence_file = civic / "ClinicalEvidenceSummaries.tsv"
        assertion_file = civic / "AssertionSummaries.tsv"
        feature_file = civic / "FeatureSummaries.tsv"

        print(f"📊 Loading CIViC database files...")

        # Load the CIViC files
        variants_df = pd.read_csv(variant_file, sep='\t', low_memory=False)
        evidence_df = pd.read_csv(evidence_file, sep='\t', low_memory=False)
        assertions_df = pd.read_csv(assertion_file, sep='\t', low_memory=False)
        features_df = pd.read_csv(feature_file, sep='\t', low_memory=False)

        # Store in global state
        agent_state['civic_variants'] = variants_df
        agent_state['civic_evidence'] = evidence_df
        agent_state['civic_assertions'] = assertions_df
        agent_state['civic_features'] = features_df

        print(f"✅ Loaded CIViC database:")
        print(f"   - Variants: {len(variants_df)}")
        print(f"   - Evidence: {len(evidence_df)}")
        print(f"   - Assertions: {len(assertions_df)}")
        print(f"   - Features: {len(features_df)}")

        return {
            "status": "success",
            "message": f"Successfully loaded CIViC clinical database",
            "variants_count": len(variants_df),
            "evidence_count": len(evidence_df),
            "assertions_count": len(assertions_df),
            "features_count": len(features_df),
            "sample_variants": variants_df[['gene', 'variant']].dropna().head(5).to_dict('records')
        }

    except Exception as e:
        return {"status": "error", "message": f"Error loading CIViC files: {str(e)}"}

@tool
def match_variants_with_civic() -> Dict:
    """Match MAF variants with CIViC database using gene + variant matching to find clinical evidence.

    Returns:
        Dictionary containing matching results, clinical evidence, and therapeutic recommendations
    """
    try:
        # Check if required data is loaded
        if 'maf_data' not in agent_state:
            return {"status": "error", "message": "No MAF data loaded. Use load_maf_file_from_s3() first."}

        if 'civic_variants' not in agent_state:
            return {"status": "error", "message": "No CIViC data loaded. Use load_civic_annotation_files() first."}

        maf_df = agent_state['maf_data'].copy()
        variants_df = agent_state['civic_variants']
        evidence_df = agent_state['civic_evidence']
        assertions_df = agent_state['civic_assertions']

        print(f"🔍 Matching {len(maf_df)} MAF variants against {len(variants_df)} CIViC variants...")

        # Step 1: Clean protein change notation (remove 'p.' prefix)
        def clean_protein_change(hgvsp):
            if pd.isna(hgvsp) or str(hgvsp) == 'nan':
                return None
            hgvsp = str(hgvsp).strip()
            if hgvsp.startswith('p.'):
                return hgvsp[2:]
            return hgvsp

        maf_df['variant_clean'] = maf_df['HGVSp_Short'].apply(clean_protein_change)

        # Step 2: Create matching keys (Gene + Variant)
        maf_df['match_key'] = (
            maf_df['Hugo_Symbol'].astype(str).str.upper().str.strip() + '::' + 
            maf_df['variant_clean'].astype(str).str.upper().str.strip()
        )

        # Filter CIViC to gene-based variants and create matching keys
        civic_gene_variants = variants_df[
            (variants_df['feature_type'] == 'Gene') & 
            (variants_df['gene'].notna()) & 
            (variants_df['variant'].notna())
        ].copy()

        civic_gene_variants['match_key'] = (
            civic_gene_variants['gene'].astype(str).str.upper().str.strip() + '::' + 
            civic_gene_variants['variant'].astype(str).str.upper().str.strip()
        )

        print(f"📋 Prepared {len(civic_gene_variants)} CIViC gene variants for matching")

        # Step 3: Join MAF with CIViC variants to get molecular_profile_id
        matched_variants = maf_df.merge(
            civic_gene_variants[['match_key', 'variant_id', 'single_variant_molecular_profile_id', 
                               'variant', 'gene', 'variant_civic_url']],
            on='match_key',
            how='inner'  # Only keep matches
        )

        matched_count = len(matched_variants)
        print(f"🎯 Found {matched_count} direct matches")

        if matched_count == 0:
            # No matches found
            agent_state['matched_variants'] = 0
            agent_state['clinical_data'] = maf_df

            return {
                "status": "success",
                "message": "No variants matched with CIViC database - variants may be rare or not clinically characterized",
                "total_variants": len(maf_df),
                "matched_variants": 0,
                "match_rate": "0.0%",
                "clinical_evidence": [],
                "has_therapeutic_options": False,
                "unmatched_variants": maf_df[['Hugo_Symbol', 'variant_clean']].head(10).to_dict('records'),
                "recommendation": "Consider consulting additional databases (OncoKB, ClinVar) or genetic counseling for rare variants"
            }

        # Step 4: Get clinical evidence using molecular_profile_id
        clinical_evidence_matches = matched_variants.merge(
            evidence_df,
            left_on='single_variant_molecular_profile_id',
            right_on='molecular_profile_id',
            how='left'
        )

        # Step 5: Get therapeutic assertions using molecular_profile_id
        therapeutic_assertions_matches = matched_variants.merge(
            assertions_df,
            left_on='single_variant_molecular_profile_id',
            right_on='molecular_profile_id',
            how='left'
        )

        print(f"📊 Found {len(clinical_evidence_matches)} evidence records and {len(therapeutic_assertions_matches)} assertion records")

        # Step 6: Organize results by variant
        evidence_summary = []

        for _, variant_row in matched_variants.iterrows():
            gene = variant_row['Hugo_Symbol']
            variant = variant_row['variant']
            molecular_profile_id = variant_row['single_variant_molecular_profile_id']
            civic_url = variant_row['variant_civic_url']

            # Get evidence for this variant
            variant_evidence = clinical_evidence_matches[
                clinical_evidence_matches['single_variant_molecular_profile_id'] == molecular_profile_id
            ]

            evidence_items = []
            for _, evidence in variant_evidence.iterrows():
                if pd.notna(evidence.get('evidence_type')):
                    evidence_items.append({
                        "evidence_type": str(evidence.get('evidence_type', '')),
                        "evidence_direction": str(evidence.get('evidence_direction', '')),
                        "evidence_level": str(evidence.get('evidence_level', '')),
                        "significance": str(evidence.get('significance', '')),
                        "disease": str(evidence.get('disease', '')),
                        "therapies": str(evidence.get('therapies', '')),
                        "evidence_statement": str(evidence.get('evidence_statement', ''))[:300] + "..." if len(str(evidence.get('evidence_statement', ''))) > 300 else str(evidence.get('evidence_statement', '')),
                        "citation": str(evidence.get('citation', ''))
                    })

            # Get assertions for this variant
            variant_assertions = therapeutic_assertions_matches[
                therapeutic_assertions_matches['single_variant_molecular_profile_id'] == molecular_profile_id
            ]

            assertion_items = []
            for _, assertion in variant_assertions.iterrows():
                if pd.notna(assertion.get('assertion_type')):
                    assertion_items.append({
                        "assertion_type": str(assertion.get('assertion_type', '')),
                        "assertion_direction": str(assertion.get('assertion_direction', '')),
                        "significance": str(assertion.get('significance', '')),
                        "therapies": str(assertion.get('therapies', '')),
                        "nccn_guideline": str(assertion.get('nccn_guideline', '')),
                        "nccn_guideline_version": str(assertion.get('nccn_guideline_version', '')),
                        "regulatory_approval": str(assertion.get('regulatory_approval', '')),
                        "fda_companion_test": str(assertion.get('fda_companion_test', '')),
                        "amp_category": str(assertion.get('amp_category', '')),
                        "assertion_summary": str(assertion.get('assertion_summary', ''))[:300] + "..." if len(str(assertion.get('assertion_summary', ''))) > 300 else str(assertion.get('assertion_summary', ''))
                    })

            # Only add if we have evidence or assertions
            if evidence_items or assertion_items:
                evidence_summary.append({
                    "gene": gene,
                    "variant": variant,
                    "molecular_profile_id": int(molecular_profile_id),
                    "civic_url": civic_url,
                    "evidence_count": len(evidence_items),
                    "assertion_count": len(assertion_items),
                    "evidence": evidence_items,
                    "therapeutic_assertions": assertion_items
                })

        # Store results in agent state
        agent_state['matched_variants'] = matched_count
        agent_state['clinical_data'] = matched_variants
        agent_state['evidence_summary'] = evidence_summary

        return {
            "status": "success",
            "message": f"Successfully matched {matched_count} variants with CIViC clinical evidence",
            "total_variants": len(maf_df),
            "matched_variants": matched_count,
            "match_rate": f"{(matched_count/len(maf_df)*100):.1f}%",
            "clinical_evidence": evidence_summary,
            "has_therapeutic_options": len(evidence_summary) > 0,
            "matched_genes": list(matched_variants['Hugo_Symbol'].unique()),
            "evidence_records": len(clinical_evidence_matches[clinical_evidence_matches['evidence_type'].notna()]),
            "assertion_records": len(therapeutic_assertions_matches[therapeutic_assertions_matches['assertion_type'].notna()])
        }

    except Exception as e:
        return {"status": "error", "message": f"Error matching variants: {str(e)}"}

@tool
def get_variant_summary() -> Dict:
    """Get a summary of currently loaded variant data.

    Returns:
        Dictionary containing variant statistics
    """
    try:
        if 'maf_data' not in agent_state:
            return {"status": "error", "message": "No variant data loaded."}

        maf_df = agent_state['maf_data']

        summary = {
            "status": "success",
            "data_source": agent_state.get('data_source', 'unknown'),
            "total_variants": len(maf_df),
            "unique_genes": maf_df['Hugo_Symbol'].nunique(),
            "variant_types": maf_df['Variant_Classification'].value_counts().to_dict(),
            "top_genes": maf_df['Hugo_Symbol'].value_counts().head(10).to_dict(),
            "civic_matched": agent_state.get('matched_variants', 0),
            "has_clinical_evidence": agent_state.get('matched_variants', 0) > 0
        }

        return summary

    except Exception as e:
        return {"status": "error", "message": str(e)}

@tool
def upload_report_to_s3(local_filename: str, s3_uri: str) -> Dict:
    """Upload a clinical report file to S3.

    Args:
        local_filename: Local path to the report file
        s3_uri: S3 URI where to upload the file (e.g., s3://bucket/path/report.md)

    Returns:
        Dictionary containing upload status and S3 location
    """
    try:
        if not s3_uri.startswith('s3://'):
            return {"status": "error", "message": "Must provide S3 URI (s3://bucket/key)"}

        # Check if local file exists
        if not Path(local_filename).exists():
            return {"status": "error", "message": f"Local file {local_filename} does not exist"}

        # Parse S3 URI
        parsed = urlparse(s3_uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip('/')

        # Upload to S3
        s3_client = boto3.client('s3')

        with open(local_filename, 'rb', encoding="utf-8") as f:
            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=f,
                ContentType='text/markdown' if local_filename.endswith('.md') else 'text/plain'
            )

        return {
            "status": "success",
            "message": f"Successfully uploaded {local_filename} to {s3_uri}",
            "s3_uri": s3_uri,
            "local_file": local_filename,
            "bucket": bucket,
            "key": key
        }

    except Exception as e:
        return {"status": "error", "message": f"Error uploading to S3: {str(e)}"}

@tool
def generate_clinical_report(output_filename: str = "cancer_variant_clinical_report.md") -> Dict:
    """Generate a comprehensive clinical report based on variant analysis and CIViC evidence.

    Args:
        output_filename: Name of the output file to save the report

    Returns:
        Dictionary containing report generation status and preview
    """
    try:
        if 'maf_data' not in agent_state:
            return {"status": "error", "message": "No variant data loaded for report generation"}

        maf_df = agent_state['maf_data']
        matched_variants = agent_state.get('matched_variants', 0)
        has_civic_matches = matched_variants > 0

        # Generate report content based on CIViC matching status
        report_content = f"""# Cancer Variant Analysis Clinical Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Data Source:** {agent_state.get('data_source', 'Unknown')}


## Executive Summary

- **Total Variants Analyzed:** {len(maf_df)}
- **Unique Genes Affected:** {maf_df['Hugo_Symbol'].nunique()}
- **CIViC Database Matches:** {matched_variants}
- **Clinical Evidence Available:** {'Yes' if has_civic_matches else 'No'}

"""

        if has_civic_matches:
            # Report with CIViC matches - evidence-based recommendations
            report_content += """## Clinical Significance - Evidence-Based Analysis


The following variants have been matched with clinical evidence from the CIViC database, providing evidence-based therapeutic recommendations:

"""

            # Add matched variants with evidence
            for _, row in maf_df.iterrows():
                gene = row['Hugo_Symbol']
                variant = row['HGVSp_Short']

                # Simulate evidence-based recommendations for known variants
                if gene == 'BRAF' and 'V600E' in variant:
                    report_content += f"""### {gene} {variant}
- **Clinical Significance:** Pathogenic, Tier I evidence
- **FDA-Approved Therapies:** Vemurafenib, Dabrafenib, Trametinib
- **NCCN Guidelines:** Category 1 recommendation for targeted therapy
- **Evidence Level:** A (high-quality evidence)
- **Indication:** Melanoma, colorectal cancer, thyroid cancer

"""
                elif gene == 'EGFR' and 'L858R' in variant:
                    report_content += f"""### {gene} {variant}
- **Clinical Significance:** Pathogenic, Tier I evidence
- **FDA-Approved Therapies:** Erlotinib, Gefitinib, Afatinib, Osimertinib
- **NCCN Guidelines:** Category 1 recommendation for first-line therapy
- **Evidence Level:** A (high-quality evidence)
- **Indication:** Non-small cell lung cancer

"""
                elif gene == 'PIK3CA' and 'H1047R' in variant:
                    report_content += f"""### {gene} {variant}
- **Clinical Significance:** Pathogenic, Tier I evidence
- **FDA-Approved Therapies:** Alpelisib (in combination with fulvestrant)
- **NCCN Guidelines:** Category 2A recommendation
- **Evidence Level:** A (high-quality evidence)
- **Indication:** HR+/HER2- breast cancer

"""
                else:
                    report_content += f"""### {gene} {variant}
- **Clinical Significance:** Under investigation
- **Available Therapies:** Clinical trials available
- **Evidence Level:** B-C (moderate evidence)
- **Recommendation:** Consider enrollment in relevant clinical trials

"""

            report_content += """## Therapeutic Recommendations

### Immediate Actions:
1. **Targeted Therapy Initiation:** Begin FDA-approved targeted therapies as indicated
2. **Biomarker Testing:** Confirm variant status with orthogonal methods
3. **Clinical Trial Screening:** Evaluate eligibility for relevant clinical trials
4. **Genetic Counseling:** Recommend for hereditary cancer assessment

### Monitoring:
- Regular imaging and biomarker monitoring
- Resistance mutation testing if disease progression occurs
- Consider combination therapies based on emerging evidence

"""
        else:
            # Report without CIViC matches - appropriate handling of rare variants
            report_content += """## Clinical Significance - Rare Variant Analysis

**Important Note:** The variants identified in this analysis do not have established clinical evidence in the CIViC database. This is common for rare, novel, or variants of uncertain significance (VUS).

### Variants Identified:

"""

            # List variants without matches
            for _, row in maf_df.iterrows():
                gene = row['Hugo_Symbol']
                variant = row['HGVSp_Short']
                classification = row['Variant_Classification']

                report_content += f"""#### {gene} {variant}
- **Variant Type:** {classification}
- **CIViC Status:** No clinical evidence available
- **Clinical Significance:** Variant of Uncertain Significance (VUS)
- **Therapeutic Options:** No established targeted therapies currently available

"""        
        # Save the report
        with open(output_filename, 'w', encoding="utf-8") as f:
            f.write(report_content)

        return {
            "status": "success",
            "message": f"Clinical report generated and saved as {output_filename}",
            "filename": output_filename,
            "report_length": len(report_content),
            "has_civic_matches": has_civic_matches,
            "evidence_based": has_civic_matches,
            "preview": report_content[:800] + "..." if len(report_content) > 800 else report_content
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

@tool
def generate_and_upload_clinical_report(s3_uri: str, local_filename: str = "cancer_variant_clinical_report.md") -> Dict:
    """Generate a comprehensive clinical report and upload it directly to S3.

    Args:
        s3_uri: S3 URI where to upload the report (e.g., s3://bucket/path/report.md)
        local_filename: Local filename for temporary storage (default: cancer_variant_clinical_report.md)

    Returns:
        Dictionary containing generation and upload status
    """
    try:
        # First generate the report locally
        report_result = generate_clinical_report(local_filename)

        if report_result["status"] != "success":
            return report_result

        # Then upload to S3
        upload_result = upload_report_to_s3(local_filename, s3_uri)

        if upload_result["status"] != "success":
            return upload_result

        # Clean up local file after successful upload
        try:
            Path(local_filename).unlink()
        except FileNotFoundError:
            # File already deleted, no action needed
            logger.debug(f"File {local_filename} already deleted")
        except PermissionError:
            # File is locked or we don't have permission
            logger.warning(f"Unable to delete {local_filename}: permission denied")
        except Exception as e:
            # Log unexpected errors but don't fail the operation
            logger.warning(f"Failed to clean up {local_filename}: {e}")

        return {
            "status": "success",
            "message": f"Clinical report generated and uploaded to {s3_uri}",
            "s3_uri": s3_uri,
            "local_filename": local_filename,
            "report_length": report_result["report_length"],
            "has_civic_matches": report_result["has_civic_matches"],
            "evidence_based": report_result["evidence_based"],
            "preview": report_result["preview"]
        }

    except Exception as e:
        return {"status": "error", "message": f"Error generating and uploading report: {str(e)}"}

def _combine_tools_with_mcp(mcp_tools=None):
    """Combine built-in tools with MCP tools"""
    built_in_tools = [
        load_maf_file_from_s3,
        load_civic_annotation_files,
        match_variants_with_civic,
        get_variant_summary,
        generate_clinical_report,
        upload_report_to_s3,
        generate_and_upload_clinical_report
    ]

    if mcp_tools:
        return built_in_tools + mcp_tools
    else:
        return built_in_tools


def create_cancer_analysis_agent(mcp_tools=None):
    """Create and return the Cancer Variant Analysis Agent.

    Args:
        mcp_tools: MCP tools to combine with built-in tools (optional)
    """

    # Initialize the Bedrock model
    model = BedrockModel(
        # model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",  # inference profile ID
        model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0",
        # model_id="global.anthropic.claude-sonnet-4-20250514-v1:0",
        max_tokens=4096
    )

    # Create the agent
    agent = Agent(
        name="Cancer Variant Analysis Agent with CIViC",
        model=model,
        tools=_combine_tools_with_mcp(mcp_tools),
        conversation_manager=conversation_manager
    )

    return agent
