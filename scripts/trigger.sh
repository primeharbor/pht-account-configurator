#!/bin/bash
#
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

MANIFEST=$1
ACCOUNT_ID=$2

if [[ -z $ACCOUNT_ID ]] ; then
    echo "USAGE: $0 <MANIFEST FILE> <ACCOUNTID>"
    exit 1
fi

RESOURCEID="NewAccountStateMachine"

if command -v jq &> /dev/null; then
    echo "jq is installed."
else
    echo "jq is not installed."
    exit 1
fi

echo "Testing $ACCOUNT_ID from Stack specified in $MANIFEST"

STACKNAME=`grep StackName: $MANIFEST  | awk '{print $2}'`
EVENT=sample-event.json

DATE=`date +%Y-%m-%d-%H-%M`
STATEMACHINE_ARN=`aws cloudformation describe-stack-resources --stack-name ${STACKNAME} --output text | grep ${RESOURCEID} | awk '{print $3}'`
if [ -z $STATEMACHINE_ARN ] ; then
    echo "Unable to find StateMachine Arn for Stack ${STACKNAME}. Aborting.."
    exit 1
fi

cat sample-event.json | jq --arg account_id "$ACCOUNT_ID" '.detail.serviceEventDetails.createAccountStatus.accountId = $account_id' > $ACCOUNT_ID-event.json

echo aws stepfunctions start-execution --state-machine-arn ${STATEMACHINE_ARN} --name "make-trigger-${ACCOUNT_ID}-${DATE}" --input file://$ACCOUNT_ID-event.json
aws stepfunctions start-execution --state-machine-arn ${STATEMACHINE_ARN} --name "make-trigger-${ACCOUNT_ID}-${DATE}" --input file://$ACCOUNT_ID-event.json

rm $ACCOUNT_ID-event.json
