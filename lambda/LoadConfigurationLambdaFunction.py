# Copyright 2024 Chris Farris <chrisf@primeharbor.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import boto3
from botocore.exceptions import ClientError
from urllib.parse import unquote
import json
import os
import yaml
from yaml import Loader, Dumper

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Lambda main routine
def handler(event, context):
    logger.info(f"Received event: {json.dumps(event, sort_keys=True)}")

    if event['detail']['serviceEventDetails']['createAccountStatus']['state'] != "SUCCEEDED":
        logger.critical(f"AWS Account is not in a SUCCEEDED state: {json.dumps(event['detail']['serviceEventDetails'])}")
        raise

    # Fetch the config file
    global_config = get_config(os.environ['BUCKET'], os.environ['CONFIG_FILE'])

    # Parse the Event
    new_aws_account_id = event['detail']['serviceEventDetails']['createAccountStatus']['accountId']
    cross_account_role_arn = f"arn:aws:iam::{new_aws_account_id}:role/{os.environ['ROLE_NAME']}"

    # Verify AssumeRole works
    client = boto3.client('sts')
    try:
        session = client.assume_role(RoleArn=cross_account_role_arn, RoleSessionName=os.environ['ROLE_SESSION_NAME'])
        creds = session['Credentials']  # Save for later
    except ClientError as e:
        logger.critical(f"Failed to assume role {cross_account_role_arn} in account {new_aws_account_id} : {e.response['Error']['Code']}")
        raise

    new_event = {
        "global_config": global_config,
        "new_aws_account_id": new_aws_account_id,
        "cross_account_role_arn": cross_account_role_arn,
        "messages": []
    }
    return(new_event)

def get_config(bucket, obj_key):
    '''get the object to index from S3 and return the parsed json'''
    s3 = boto3.client('s3')
    try:
        response = s3.get_object(
            Bucket=bucket,
            Key=unquote(obj_key)
        )
        return(yaml.load(response['Body'].read(), Loader=Loader))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            logger.error("Unable to find config s3://{}/{}".format(bucket, obj_key))
        else:
            logger.error("Error getting config s3://{}/{}: {}".format(bucket, obj_key, e))
        return(None)

#EOF