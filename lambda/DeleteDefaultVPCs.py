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

    if 'default_vpc' not in event['global_config']:
        # Nothing to do
        return(event)

    if 'delete_default_vpc' in event['global_config']['default_vpc'] and event['global_config']['default_vpc']['delete_default_vpc']:

        regions = get_regions(event['cross_account_role_arn'])
        for r in regions:
            if 'preserve_vpc_regions' in event['global_config']['default_vpc'] and r in event['global_config']['default_vpc']['preserve_vpc_regions']:
                event['messages'].append(f"Skipping deleting the default VPC in {r} in {event['new_aws_account_id']}")
                continue

            logger.info(f"Deleting Default VPC in {r} in {event['new_aws_account_id']}")
            event['messages'].append(f"Deleting Default VPC in {r} in {event['new_aws_account_id']}")
            process_region(r, event['cross_account_role_arn'])

    return(event)

def delete_igw(vpc):
    for igw in vpc.internet_gateways.all():
        logger.info("Detaching {}, VPC:{}".format(igw.id,vpc.id))
        igw.detach_from_vpc(VpcId=vpc.id)
        logger.info("Deleting {}, VPC:{}".format(igw.id,vpc.id))
        igw.delete()

def delete_eigw(vpc):
    client = vpc.meta.client
    paginator = client.get_paginator('describe_egress_only_internet_gateways')
    for page in paginator.paginate():
        for eigw in page['EgressOnlyInternetGateways']:
            for attachment in eigw['Attachments']:
                if attachment['VpcId'] == vpc.id and attachment['State'] == 'attached':
                    logger.info("Deleting {}, VPC:{}".format(eigw['EgressOnlyInternetGatewayId'],vpc.id))
                    client.delete_egress_only_internet_gateway(EgressOnlyInternetGatewayId=eigw['EgressOnlyInternetGatewayId'])
                    break

def delete_subnet(vpc):
    for subnet in vpc.subnets.all():
        logger.info("Deleting {}, VPC:{}".format(subnet.id,vpc.id))
        subnet.delete()

def delete_sg(vpc):
    for sg in filter(lambda x:x.group_name != 'default', vpc.security_groups.all()): #exclude default SG:
        logger.info("Deleting {}, VPC:{}".format(sg.id,vpc.id))
        sg.delete()

def delete_rtb(vpc):
    for rtb in vpc.route_tables.all():
        rt_is_main = False
        # skip deleting main route tables
        for attr in rtb.associations_attribute:
            if attr['Main']:
                rt_is_main = True
        if rt_is_main:
            continue
        logger.info("Deleting {}, VPC:{}".format(rtb.id,vpc.id))
        rtb.delete()

def delete_acl(vpc):
    for acl in vpc.network_acls.all():
        if acl.is_default:
            # skip deleting default acl
            continue
        logger.info("Deleting {}, VPC:{}".format(acl.id,vpc.id))
        acl.delete()

def delete_pcx(vpc):
    pcxs = list(vpc.accepted_vpc_peering_connections.all()) + list(vpc.requested_vpc_peering_connections.all())
    for pcx in pcxs:
        if pcx.status['Code'] == 'deleted':
            # vpc peering connections already deleted
            continue
        logger.info("Deleting {}, VPC:{}".format(pcx.status,vpc.id))
        pcx.delete()

def delete_endpoints(vpc):
    client = vpc.meta.client
    paginator = client.get_paginator('describe_vpc_endpoints')
    for page in paginator.paginate(Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc.id]},
                    {'Name': 'vpc-endpoint-state', 'Values': ['pendingAcceptance', 'pending', 'available', 'rejected', 'failed']},
                ]):
        for endpoint in page['VpcEndpoints']:
            logger.info("Deleting {}, VPC:{}".format(endpoint['VpcEndpointId'],vpc.id))
            client.delete_vpc_endpoints(VpcEndpointIds=[endpoint['VpcEndpointId']])

def delete_vgw(vpc):
    client = vpc.meta.client
    response = client.describe_vpn_gateways(Filters=[
                    {'Name': 'attachment.vpc-id', 'Values': [vpc.id]},
                    {'Name': 'state', 'Values': ['pending', 'available']},
                ])
    for vgw in response['VpnGateways']:
        for attachment in vgw['VpcAttachments']:
            if attachment['State'] in ['attaching','attached']:
                logger.info("Detaching {}, from VPC:{}".format(vgw['VpnGatewayId'],vpc.id))
                client.detach_vpn_gateway(VpcId=vpc.id, VpnGatewayId=vgw['VpnGatewayId'])
                break
        response = client.describe_vpn_connections(Filters=[{'Name': 'vpn-gateway-id', 'Values': [vgw['VpnGatewayId']]}])
        for vpn_connection in response['VpnConnections']:
            if vpn_connection['State'] in ['pending','available']:
                logger.info("Deleting {}, from VPC:{}".format(vpn_connection['VpnConnectionId'],vpc.id))
                client.delete_vpn_connection(VpnConnectionId=vpn_connection['VpnConnectionId'])
        logger.info("Deleting {}, VPC:{}".format(vgw['VpnGatewayId'],vpc.id))
        client.delete_vpn_gateway(VpnGatewayId=vgw['VpnGatewayId'])

def delete_vpc(vpc,region):

    network_interfaces = list(vpc.network_interfaces.all())
    if network_interfaces:
        logger.warning("Elastic Network Interfaces exist in the VPC:{}, skipping delete".format(vpc.id))
    else:
        logger.info("Deleting default VPC:{}, region:{}".format(vpc.id,region))
        try:
            vpc_resources = {
                # dependency order from https://aws.amazon.com/premiumsupport/knowledge-center/troubleshoot-dependency-error-delete-vpc/
                'internet_gateways': delete_igw,
                'egress_only_internet_gateways': delete_eigw,
                'subnets': delete_subnet,
                'route_tables': delete_rtb,
                'network_acls': delete_acl,
                'vpc_peering_connections': delete_pcx,
                'vpc_endpoints': delete_endpoints,
                'security_groups': delete_sg,
                # instances (we do not delete this for safety)
                'virtual_private_gateways': delete_vgw,
            }
            for resource_type in vpc_resources:
                vpc_resources[resource_type](vpc)

            vpc.delete()

        except ClientError as e:
            if e.response['Error']['Code'] == 'DependencyViolation':
                logger.error("VPC:{} can't be delete due to dependency, {}".format(vpc.id, e))
            else:
                raise
        logger.info("Successfully deleted default VPC:{}, region:{}".format(vpc.id,region))

def process_region(region, cross_account_role_arn):
    logger.info(f"Processing region {region}")
    ec2_resource = get_resource('ec2', cross_account_role_arn, region=region)

    vpcs = []
    for vpc in ec2_resource.vpcs.filter(Filters=[{'Name': 'isDefault', 'Values': ['true']}]):
        logger.info(f'Found {vpc}')
        vpcs.append(vpc)
    if vpcs:
        for vpc in vpcs:
            delete_vpc(vpc,region)
    else:
        logger.info("No Default VPC to to be deleted in region:{}".format(region))

    return

