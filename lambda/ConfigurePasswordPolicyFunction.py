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

    if 'account_password_policy' not in event['global_config']:
        # Nothing to do
        return(event)

    client = get_client('iam', event['cross_account_role_arn'])
    if event['global_config']['account_password_policy']['update_account_password_policy']:
        logger.info(f"Applying Password Policy in {event['new_aws_account_id']}")
        event['messages'].append(f"Applying Password Policy in {event['new_aws_account_id']}")
        policy = event['global_config']['account_password_policy']['password_policy']
        response = client.update_account_password_policy(
            MinimumPasswordLength       = policy['MinimumPasswordLength'],
            RequireSymbols              = policy['RequireSymbols'],
            RequireNumbers              = policy['RequireNumbers'],
            RequireUppercaseCharacters  = policy['RequireUppercaseCharacters'],
            RequireLowercaseCharacters  = policy['RequireLowercaseCharacters'],
            AllowUsersToChangePassword  = policy['AllowUsersToChangePassword'],
            MaxPasswordAge              = policy['MaxPasswordAge'],
            PasswordReusePrevention     = policy['PasswordReusePrevention'],
            HardExpiry                  = policy['HardExpiry'],
        )

    return(event)