# /*********************************************************************************************************************
# *  Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.                                           *
# *                                                                                                                    *
# *  Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance    *
# *  with the License. A copy of the License is located at                                                             *
# *                                                                                                                    *
# *      http://www.apache.org/licenses/LICENSE-2.0                                                                    *
# *                                                                                                                    *
# *  or in the 'license' file accompanying this file. This file is distributed on an 'AS IS' BASIS, WITHOUT WARRANTIES *
# *  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions    *
# *  and limitations under the License.                                                                                *
# *********************************************************************************************************************/

try:
    from crhelper import CfnResource
    import logging
    import boto3
except ImportError as e:
    raise Exception(f"Import failed: {e}") 

logger = logging.getLogger(__name__)
# Initialise the helper, all inputs are optional, this example shows the defaults
helper = CfnResource(json_logging=False, log_level='DEBUG', boto_level='CRITICAL')


# Initiate client
try:
    print("Attempt to initiate client")
    omics_session = boto3.Session()
    omics_client = omics_session.client('omics')
    print("Attempt to initiate client complete")
except Exception as e:
    helper.init_failure(e)


@helper.create
def create(event, context):
    logger.info("Got Create")
    start_workflow(event, context)


@helper.update
def update(event, context):
    logger.info("Got Update")
    start_workflow(event, context)


@helper.delete
def delete(event, context):
    logger.info("Got Delete")
    pass
    # Delete never returns anything. Should not fail if the underlying resources are already deleted. Desired state.

@helper.poll_create
def poll_create(event, context):
    logger.info("Got Create poll")
    return get_workflow_run_status(event, context)


@helper.poll_update
def poll_update(event, context):
    logger.info("Got Update poll")
    return 


@helper.poll_delete
def poll_delete(event, context):
    logger.info("Got Delete poll")
    return True

def handler(event, context):
    helper(event, context)

# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/omics/client/start_run.html
def start_workflow(event, context):
    workflow_id = event['ResourceProperties']['WorkflowId']
    role_arn = event['ResourceProperties']['JobRoleArn']
    output_s3_path = event['ResourceProperties']['OutputS3Path']
    run_name = event['ResourceProperties']['RunName']
    params = {
        "normal_reads": event['ResourceProperties']['ParamNormalBam'],
        "normal_reads_index": event['ResourceProperties']['ParamNormalBamIndex'],
        "normal_sample_name": event['ResourceProperties']['ParamNormalSampleName'],
        "tumor_reads": event['ResourceProperties']['ParamTumorBam'],
        "tumor_reads_index": event['ResourceProperties']['ParamTumorBamIndex'],
        "tumor_sample_name": event['ResourceProperties']['ParamTumorSampleName'],
        "ref_fasta": event['ResourceProperties']['ParamReferenceFasta'],
        "ref_fai": event['ResourceProperties']['ParamReferenceFastaIndex'],
        "ref_dict": event['ResourceProperties']['ParamReferenceDict'],
        "vcf2maf_output": event['ResourceProperties']['ParamVcfMaf'],
        "small_task_cpu": int(event['ResourceProperties']['ParamSmallTaskCpu']),
        "small_task_mem": int(event['ResourceProperties']['ParamSmallTaskMemory']),
        "intervals": event['ResourceProperties']['ParamIntervals'],
        "aws_region": event['ResourceProperties']['ParamAwsRegion']
    }

    try:
        print("Attempt to start workflow run")
        response = omics_client.start_run(
            workflowId=workflow_id,
            name=run_name,
            roleArn=role_arn,
            parameters=params,
            outputUri=output_s3_path,
            workflowType='PRIVATE',
            storageType='DYNAMIC'
            )
    except Exception as e:
       raise Exception( "Unexpected error : " +    e.__str__())
    logger.info(response)
    helper.Data.update({"WorkflowRunId": response['id']})

def get_workflow_run_status(event, context):
    workflow_run_id = helper.Data.get('WorkflowRunId', None)
    if not workflow_run_id:
        msg = "Unable to find workflow run id"
        logger.info(msg)
        return None

    try:
        response = omics_client.get_run(id=workflow_run_id)
    except Exception as e:
       raise Exception( "Unexpected error : " +    e.__str__())
    status = response['status']
    
    if status in ['PENDING', 'STARTING', 'RUNNING', 'STOPPING']:
        logger.info(status)
        return None
    else:
        if status in ['COMPLETED']:
            logger.info(status)
            return True
        else:
            msg = f"Workflow Run ID {workflow_run_id} has status {status}, exiting"
            logger.info(msg)
            raise ValueError(msg)
