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

from botocore.exceptions import ClientError
from urllib.parse import unquote
from yaml import Loader, Dumper
import boto3
import json
import os
import yaml
import logging

logger = logging.getLogger()

def get_client(type, cross_account_role_arn, region=None):
    """
    Returns a boto3 client for the service "type" with credentials in the target account.
    Optionally you can specify the region for the client and the session_name for the AssumeRole.
    """
    client = boto3.client('sts')
    try:
        session = client.assume_role(RoleArn=cross_account_role_arn, RoleSessionName=os.environ['ROLE_SESSION_NAME'])
        creds = session['Credentials']  # Save for later
    except ClientError as e:
        logger.critical(f"Failed to assume role {cross_account_role_arn}: {e.response['Error']['Code']}")
        return(None)
    client = boto3.client(type,
        aws_access_key_id = creds['AccessKeyId'],
        aws_secret_access_key = creds['SecretAccessKey'],
        aws_session_token = creds['SessionToken'],
        region_name = region)
    return(client)


def get_resource(type, cross_account_role_arn, region=None):
    """
    Returns a boto3 client for the service "type" with credentials in the target account.
    Optionally you can specify the region for the client and the session_name for the AssumeRole.
    """
    client = boto3.client('sts')
    try:
        session = client.assume_role(RoleArn=cross_account_role_arn, RoleSessionName=os.environ['ROLE_SESSION_NAME'])
        creds = session['Credentials']  # Save for later
    except ClientError as e:
        logger.critical(f"Failed to assume role {cross_account_role_arn}: {e.response['Error']['Code']}")
        return(None)
    resource = boto3.resource(type,
        aws_access_key_id = creds['AccessKeyId'],
        aws_secret_access_key = creds['SecretAccessKey'],
        aws_session_token = creds['SessionToken'],
        region_name = region)
    return(resource)


def get_regions(cross_account_role_arn):
    '''Return a list of regions with us-east-1 first. If --region was specified, return a list wth just that'''

    # otherwise return all the regions, us-east-1 first
    ec2 = get_client('ec2', cross_account_role_arn, region="us-east-1")
    response = ec2.describe_regions()
    output = ['us-east-1']
    for r in response['Regions']:
        # return us-east-1 first, but dont return it twice
        if r['RegionName'] == "us-east-1":
            continue
        output.append(r['RegionName'])
    return(output)