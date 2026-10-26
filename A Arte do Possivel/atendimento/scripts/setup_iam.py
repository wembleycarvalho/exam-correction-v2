"""
Setup IAM roles and policies.
Uso: source .env && python3 scripts/setup_iam.py
"""
import boto3
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, set_env, get_env

ACCOUNT_ID = require_env('AWS_ACCOUNT_ID')
REGION = get_env('AWS_REGION', 'us-east-1')
iam = boto3.client('iam')

roles = {
    'SocialMessagingConnectRole': {
        'trust': {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": ["social-messaging.amazonaws.com", "sms-voice.amazonaws.com"]}, "Action": "sts:AssumeRole"}]},
        'policy_name': 'SocialMessagingConnectPolicy',
        'policy': {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["connect:SendChatIntegrationEvent", "connect:StartChatContact", "connect:ImportPhoneNumber", "connect:DescribePhoneNumber", "connect:DescribeInstance", "connect:SendIntegrationEvent"], "Resource": "*"}]}
    },
    'AgentCoreGatewayRole': {
        'trust': {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "bedrock-agentcore.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
        'policy_name': 'AgentCoreGatewayLambdaPolicy',
        'policy': {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["lambda:InvokeFunction"], "Resource": [f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:mcp-catalogo-cursos", f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:connect-user-lookup"]}]}
    },
    'ConnectHarnessLambdaRole': {
        'trust': {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
        'policy_name': 'ConnectHarnessLambdaPolicy',
        'policy': {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["cognito-idp:InitiateAuth"], "Resource": "*"}, {"Effect": "Allow", "Action": ["bedrock-agentcore:InvokeHarness", "bedrock-agentcore:InvokeAgentRuntime"], "Resource": "*"}, {"Effect": "Allow", "Action": ["social-messaging:SendWhatsAppMessage"], "Resource": "*"}, {"Effect": "Allow", "Action": ["lambda:InvokeFunction"], "Resource": f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:connect-harness-async"}]}
    },
    'LexFulfillmentLambdaRole': {
        'trust': {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
        'policy_name': 'LexFulfillmentPolicy',
        'policy': {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["dynamodb:GetItem", "dynamodb:Scan", "dynamodb:Query"], "Resource": "*"}, {"Effect": "Allow", "Action": ["bedrock-agentcore:InvokeHarness", "bedrock-agentcore:InvokeAgentRuntime"], "Resource": "*"}, {"Effect": "Allow", "Action": ["cognito-idp:InitiateAuth"], "Resource": "*"}, {"Effect": "Allow", "Action": ["social-messaging:SendWhatsAppMessage"], "Resource": "*"}]}
    },
    'LambdaMCPCursosRole': {
        'trust': {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
        'managed_policies': ['arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole', 'arn:aws:iam::aws:policy/AmazonDynamoDBReadOnlyAccess']
    }
}

for role_name, config in roles.items():
    try:
        iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=json.dumps(config['trust']))
        print(f'{role_name}: created')
    except iam.exceptions.EntityAlreadyExistsException:
        print(f'{role_name}: exists')

    if 'lambda' in str(config['trust']):
        iam.attach_role_policy(RoleName=role_name, PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole')

    if 'policy_name' in config:
        policy_arn = f'arn:aws:iam::{ACCOUNT_ID}:policy/{config["policy_name"]}'
        try:
            iam.create_policy(PolicyName=config['policy_name'], PolicyDocument=json.dumps(config['policy']))
        except iam.exceptions.EntityAlreadyExistsException:
            pass
        iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)

    for mp in config.get('managed_policies', []):
        iam.attach_role_policy(RoleName=role_name, PolicyArn=mp)

# Propagar ARNs pro .env
set_env('GATEWAY_ROLE_ARN', f'arn:aws:iam::{ACCOUNT_ID}:role/AgentCoreGatewayRole')

print('\nDone!')
