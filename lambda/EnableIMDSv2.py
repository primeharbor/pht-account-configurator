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

from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Lambda main routine
def handler(event, context):
    logger.info(f"Received event: {json.dumps(event, sort_keys=True)}")

    if 'require_imdsv2' not in event['global_config']:
        # Nothing to do
        return(event)

    regions = get_regions(event['cross_account_role_arn'])

    for r in regions:
        client = get_client('ec2', event['cross_account_role_arn'], region=r)
        logger.info(f"Enabling IMDSv2 in {r} in {event['new_aws_account_id']}")
        event['messages'].append(f"Enabling IMDSv2 in {r} in {event['new_aws_account_id']}")

        settings = event['global_config']['require_imdsv2']

        response = client.modify_instance_metadata_defaults(
            HttpTokens=settings.get('HttpTokens', 'no-preference'),
            HttpPutResponseHopLimit=settings.get('HttpPutResponseHopLimit', 1),
            HttpEndpoint=settings.get('HttpEndpoint', 'no-preference'),
            InstanceMetadataTags=settings.get('InstanceMetadataTags', 'no-preference')
        )

    return(event)