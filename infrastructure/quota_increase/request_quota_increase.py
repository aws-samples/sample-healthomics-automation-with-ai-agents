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
    logger.info("Attempt to initiate client")
    sq_session = boto3.Session()
    sq_client = sq_session.client('service-quotas')
    logger.info("Attempt to initiate client complete")
except Exception as e:
    helper.init_failure(e)


@helper.create
def create(event, context):
    logger.info("Got Create")
    request_service_quota_increase(event, context)


@helper.update
def update(event, context):
    logger.info("Got Update")
    request_service_quota_increase(event, context)


@helper.delete
def delete(event, context):
    logger.info("Got Delete")
    pass
    # Delete never returns anything. Should not fail if the underlying resources are already deleted. Desired state.

@helper.poll_create
def poll_create(event, context):
    logger.info("Got Create poll")
    return get_service_quota_increase_status(event, context)


@helper.poll_update
def poll_update(event, context):
    logger.info("Got Update poll")
    return get_service_quota_increase_status(event, context)


@helper.poll_delete
def poll_delete(event, context):
    logger.info("Got Delete poll")
    return True

def handler(event, context):
    helper(event, context)

def request_service_quota_increase(event, context):
    request_type = event['RequestType']
    properties = event['ResourceProperties']
    
    # Required parameters
    service_code = properties['ServiceCode']
    quota_code = properties['QuotaCode']
    desired_value = float(properties['DesiredValue'])
    
    if request_type == 'Create' or request_type == 'Update':
        if is_current_quota_greater_than_desired(event, context):
            msg = f"Current quota value is greater than desired value, no need to request quota increase"
            logger.info(msg)
            helper.Data.update({"RequestId": 'NA'})
        else:
            logger.info(f"Current quota value is less than desired value, requesting quota increase")
            response = sq_client.request_service_quota_increase(
                ServiceCode=service_code,
                QuotaCode=quota_code,
                DesiredValue=desired_value
            )
            request_id = response['RequestedQuota']['Id']
            logger.info(response)
            helper.Data.update({"RequestId": request_id})

def get_service_quota_increase_status(event, context):
    request_id = helper.Data.get('RequestId', None)
    if not request_id:
        msg = "Unable to find Request ID"
        logger.info(msg)
        return None
    if request_id == 'NA':
        logger.info("Quota increase not required")
        return True

    try:
        response = sq_session.get_requested_service_quota_change(RequestId=request_id)
    except Exception as e:
       raise Exception( "Unexpected error : " +    e.__str__())
    status = response['RequestedQuota']['Status']
    
    if status in ['PENDING','CASE_OPENED']:
        logger.info(status)
        return None
    elif status in ['DENIED','CASE_CLOSED','NOT_APPROVED','INVALID_REQUEST']:
        logger.info(status)
        raise Exception(f"Request Id {request_id} has status {status}, exiting")
    elif status in ['APPROVED']:
        logger.info(status)
        return True
    else:
        msg = f"Request Id {request_id} has status {status}, exiting"
        logger.info(msg)
        raise ValueError(msg)

def is_current_quota_greater_than_desired(event, context):
    request_type = event['RequestType']
    properties = event['ResourceProperties']
    
    # Required parameters
    service_code = properties['ServiceCode']
    quota_code = properties['QuotaCode']
    desired_value = float(properties['DesiredValue'])
    
    if request_type == 'Create' or request_type == 'Update':
        # Request quota increase
        response = sq_client.get_service_quota(
            ServiceCode=service_code,
            QuotaCode=quota_code
        )
        current_quota = response['Quota']['Value']
            
    logger.info(f"Current quota: {current_quota}")
    helper.Data.update({"CurrentQuotaValue": current_quota})
    if current_quota >= desired_value:
        return True
    else:
        return False

