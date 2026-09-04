"""
Setup infraestrutura para segunda via de boleto:
- S3 bucket com lifecycle 7 dias
- IAM Role LambdaBoletoRole
- Atualiza AgentCoreGatewayLambdaPolicy

Uso: source .env && python3 scripts/setup_boleto_infra.py
"""
import boto3
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env, set_env

REGION = get_env('AWS_REGION', 'us-east-1')
ACCOUNT_ID = require_env('AWS_ACCOUNT_ID')
BUCKET_NAME = f'boletos-demo-{ACCOUNT_ID}'

s3 = boto3.client('s3', region_name=REGION)
iam = boto3.client('iam')

# ============================================================
# STEP 1: S3 Bucket
# ============================================================
print('=== S3 Bucket ===')
try:
    s3.create_bucket(Bucket=BUCKET_NAME)
    print(f'  Created: {BUCKET_NAME}')
except s3.exceptions.BucketAlreadyOwnedByYou:
    print(f'  Exists: {BUCKET_NAME}')
except Exception as e:
    if 'BucketAlreadyExists' in str(e):
        print(f'  Exists: {BUCKET_NAME}')
    else:
        raise

# Lifecycle rule: delete after 7 days
s3.put_bucket_lifecycle_configuration(
    Bucket=BUCKET_NAME,
    LifecycleConfiguration={
        'Rules': [{
            'ID': 'delete-after-7-days',
            'Status': 'Enabled',
            'Filter': {'Prefix': ''},
            'Expiration': {'Days': 7}
        }]
    }
)
print('  Lifecycle: delete after 7 days')
set_env('S3_BUCKET_BOLETOS', BUCKET_NAME)

# ============================================================
# STEP 2: IAM Role LambdaBoletoRole
# ============================================================
print('\n=== IAM Role: LambdaBoletoRole ===')
trust = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole"
    }]
}

try:
    iam.create_role(RoleName='LambdaBoletoRole', AssumeRolePolicyDocument=json.dumps(trust))
    print('  Role created')
except iam.exceptions.EntityAlreadyExistsException:
    print('  Role exists')

# Attach basic execution
iam.attach_role_policy(
    RoleName='LambdaBoletoRole',
    PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
)

# Attach DynamoDB read
iam.attach_role_policy(
    RoleName='LambdaBoletoRole',
    PolicyArn='arn:aws:iam::aws:policy/AmazonDynamoDBReadOnlyAccess'
)

# Custom policy for S3 + Social Messaging
policy_name = 'LambdaBoletoPolicy'
policy_doc = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:PutObject", "s3:GetObject"],
            "Resource": f"arn:aws:s3:::{BUCKET_NAME}/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "social-messaging:PostWhatsAppMessageMedia",
                "social-messaging:SendWhatsAppMessage"
            ],
            "Resource": "*"
        }
    ]
}

policy_arn = f'arn:aws:iam::{ACCOUNT_ID}:policy/{policy_name}'
try:
    iam.create_policy(PolicyName=policy_name, PolicyDocument=json.dumps(policy_doc))
    print(f'  Policy created: {policy_name}')
except iam.exceptions.EntityAlreadyExistsException:
    # Update existing policy
    pol = iam.get_policy(PolicyArn=policy_arn)
    versions = iam.list_policy_versions(PolicyArn=policy_arn)['Versions']
    for v in versions:
        if not v['IsDefaultVersion']:
            iam.delete_policy_version(PolicyArn=policy_arn, VersionId=v['VersionId'])
    iam.create_policy_version(PolicyArn=policy_arn, PolicyDocument=json.dumps(policy_doc), SetAsDefault=True)
    print(f'  Policy updated: {policy_name}')

iam.attach_role_policy(RoleName='LambdaBoletoRole', PolicyArn=policy_arn)
print('  Policies attached')

# ============================================================
# STEP 3: Update AgentCoreGatewayLambdaPolicy
# ============================================================
print('\n=== Update AgentCoreGatewayLambdaPolicy ===')
gw_policy_arn = f'arn:aws:iam::{ACCOUNT_ID}:policy/AgentCoreGatewayLambdaPolicy'
lambda_boleto_arn = f'arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:mcp-boleto'

try:
    pol = iam.get_policy(PolicyArn=gw_policy_arn)
    ver = iam.get_policy_version(PolicyArn=gw_policy_arn, VersionId=pol['Policy']['DefaultVersionId'])
    doc = ver['PolicyVersion']['Document']

    resources = doc['Statement'][0]['Resource']
    if isinstance(resources, str):
        resources = [resources]
    if lambda_boleto_arn not in resources:
        resources.append(lambda_boleto_arn)
        doc['Statement'][0]['Resource'] = resources
        versions = iam.list_policy_versions(PolicyArn=gw_policy_arn)['Versions']
        for v in versions:
            if not v['IsDefaultVersion']:
                iam.delete_policy_version(PolicyArn=gw_policy_arn, VersionId=v['VersionId'])
        iam.create_policy_version(PolicyArn=gw_policy_arn, PolicyDocument=json.dumps(doc), SetAsDefault=True)
        print(f'  Added mcp-boleto to gateway policy')
    else:
        print(f'  mcp-boleto already in gateway policy')
except Exception as e:
    print(f'  Error: {e}')

print('\nDone!')
