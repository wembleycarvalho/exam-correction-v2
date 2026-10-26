"""
Infra da migracao de voz WhatsApp <-> Amazon Connect (nao-destrutivo).
Cria/atualiza (idempotente):
  - DynamoDB whatsapp-connect-sessions (PK contactId, GSI customerId-index)
  - S3 bucket whatsapp-media-{account} (lifecycle 1 dia)
  - SNS topic whatsapp-inbound (policy: EUM Social pode publicar)
  - SNS topic whatsapp-connect-streaming (policy: Connect pode publicar)
  - IAM role LambdaWppGatewayRole (dynamodb, s3, socialmessaging, connect, transcribe, polly, logs)

Propaga ARNs/nomes pro .env. NAO mexe no event destination (isso e o flip, separado).

Uso: source .env && python3 scripts/setup_voice_infra.py
"""
import boto3
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env, set_env

REGION = get_env('AWS_REGION', 'us-east-1')
ACCOUNT_ID = require_env('AWS_ACCOUNT_ID')

# IDs corretos (o .env pode estar com instance antigo — ver steering connect-resources)
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
INSTANCE_ARN = f'arn:aws:connect:{REGION}:{ACCOUNT_ID}:instance/{INSTANCE_ID}'

SESSIONS_TABLE = 'whatsapp-connect-sessions'
MEDIA_BUCKET = f'whatsapp-media-{ACCOUNT_ID}'
INBOUND_TOPIC = 'whatsapp-inbound'
STREAMING_TOPIC = 'whatsapp-connect-streaming'
ROLE_NAME = 'LambdaWppGatewayRole'

ddb = boto3.client('dynamodb', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)
sns = boto3.client('sns', region_name=REGION)
iam = boto3.client('iam')


# ============================================================ DynamoDB
print('=== DynamoDB: whatsapp-connect-sessions ===')
try:
    ddb.create_table(
        TableName=SESSIONS_TABLE,
        AttributeDefinitions=[
            {'AttributeName': 'contactId', 'AttributeType': 'S'},
            {'AttributeName': 'customerId', 'AttributeType': 'S'},
        ],
        KeySchema=[{'AttributeName': 'contactId', 'KeyType': 'HASH'}],
        GlobalSecondaryIndexes=[{
            'IndexName': 'customerId-index',
            'KeySchema': [{'AttributeName': 'customerId', 'KeyType': 'HASH'}],
            'Projection': {'ProjectionType': 'ALL'},
        }],
        BillingMode='PAY_PER_REQUEST',
    )
    print('  Criada. Aguardando ficar ativa...')
    ddb.get_waiter('table_exists').wait(TableName=SESSIONS_TABLE)
except ddb.exceptions.ResourceInUseException:
    print('  Ja existe.')
set_env('SESSIONS_TABLE', SESSIONS_TABLE)


# ============================================================ S3
print('\n=== S3: media bucket ===')
try:
    s3.create_bucket(Bucket=MEDIA_BUCKET)
    print(f'  Criado: {MEDIA_BUCKET}')
except s3.exceptions.BucketAlreadyOwnedByYou:
    print(f'  Ja existe: {MEDIA_BUCKET}')
except Exception as e:
    if 'BucketAlreadyExists' in str(e):
        print(f'  Ja existe: {MEDIA_BUCKET}')
    else:
        raise
# bloquear acesso publico
s3.put_public_access_block(
    Bucket=MEDIA_BUCKET,
    PublicAccessBlockConfiguration={
        'BlockPublicAcls': True, 'IgnorePublicAcls': True,
        'BlockPublicPolicy': True, 'RestrictPublicBuckets': True})
s3.put_bucket_lifecycle_configuration(
    Bucket=MEDIA_BUCKET,
    LifecycleConfiguration={'Rules': [{
        'ID': 'expire-1d', 'Status': 'Enabled',
        'Filter': {'Prefix': ''}, 'Expiration': {'Days': 1}}]})
print('  Public access bloqueado + lifecycle 1 dia')
set_env('MEDIA_BUCKET', MEDIA_BUCKET)


# ============================================================ SNS topics
def ensure_topic(name):
    arn = sns.create_topic(Name=name)['TopicArn']  # idempotente
    print(f'  Topic: {arn}')
    return arn

print('\n=== SNS topics ===')
inbound_arn = ensure_topic(INBOUND_TOPIC)
streaming_arn = ensure_topic(STREAMING_TOPIC)

# Policy do inbound: EUM Social publica
inbound_policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "AllowEUMSocialPublish",
        "Effect": "Allow",
        "Principal": {"Service": "social-messaging.amazonaws.com"},
        "Action": "sns:Publish",
        "Resource": inbound_arn,
        "Condition": {"StringEquals": {"aws:SourceAccount": ACCOUNT_ID}},
    }],
}
sns.set_topic_attributes(TopicArn=inbound_arn, AttributeName='Policy',
                         AttributeValue=json.dumps(inbound_policy))

# Policy do streaming: Connect publica
streaming_policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "AllowConnectPublish",
        "Effect": "Allow",
        "Principal": {"Service": "connect.amazonaws.com"},
        "Action": "sns:Publish",
        "Resource": streaming_arn,
        "Condition": {"StringEquals": {"aws:SourceAccount": ACCOUNT_ID}},
    }],
}
sns.set_topic_attributes(TopicArn=streaming_arn, AttributeName='Policy',
                         AttributeValue=json.dumps(streaming_policy))
print('  Policies aplicadas (EUM -> inbound, Connect -> streaming)')

set_env('WPP_INBOUND_TOPIC_ARN', inbound_arn)
set_env('WPP_STREAMING_TOPIC_ARN', streaming_arn)


# ============================================================ IAM role
print('\n=== IAM: LambdaWppGatewayRole ===')
trust = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
}
try:
    iam.create_role(RoleName=ROLE_NAME, AssumeRolePolicyDocument=json.dumps(trust),
                    Description='Role dos gateways de voz WhatsApp <-> Connect')
    print('  Role criada')
except iam.exceptions.EntityAlreadyExistsException:
    print('  Role ja existe')

iam.attach_role_policy(
    RoleName=ROLE_NAME,
    PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole')

policy_name = 'LambdaWppGatewayPolicy'
policy_arn = f'arn:aws:iam::{ACCOUNT_ID}:policy/{policy_name}'
policy_doc = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "Dynamo",
            "Effect": "Allow",
            "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
                       "dynamodb:DeleteItem", "dynamodb:Query"],
            "Resource": [
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT_ID}:table/{SESSIONS_TABLE}",
                f"arn:aws:dynamodb:{REGION}:{ACCOUNT_ID}:table/{SESSIONS_TABLE}/index/*",
            ],
        },
        {
            "Sid": "S3Media",
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
            "Resource": f"arn:aws:s3:::{MEDIA_BUCKET}/*",
        },
        {
            "Sid": "S3List",
            "Effect": "Allow",
            "Action": ["s3:ListBucket"],
            "Resource": f"arn:aws:s3:::{MEDIA_BUCKET}",
        },
        {
            "Sid": "SocialMessaging",
            "Effect": "Allow",
            "Action": ["social-messaging:GetWhatsAppMessageMedia",
                       "social-messaging:PostWhatsAppMessageMedia",
                       "social-messaging:SendWhatsAppMessage"],
            "Resource": "*",
        },
        {
            "Sid": "ConnectChat",
            "Effect": "Allow",
            "Action": ["connect:StartChatContact", "connect:StartContactStreaming",
                       "connect:StopContactStreaming", "connect:DescribeContact",
                       "connect:GetContactAttributes"],
            "Resource": [INSTANCE_ARN,
                         f"{INSTANCE_ARN}/contact-flow/*",
                         f"{INSTANCE_ARN}/contact/*"],
        },
        {
            "Sid": "TranscribeStreaming",
            "Effect": "Allow",
            "Action": ["transcribe:StartStreamTranscription"],
            "Resource": "*",
        },
        {
            "Sid": "Polly",
            "Effect": "Allow",
            "Action": ["polly:SynthesizeSpeech"],
            "Resource": "*",
        },
        {
            "Sid": "BedrockVision",
            "Effect": "Allow",
            "Action": ["bedrock:InvokeModel"],
            "Resource": "*",
        },
    ],
}

def upsert_policy():
    try:
        iam.create_policy(PolicyName=policy_name, PolicyDocument=json.dumps(policy_doc))
        print(f'  Policy criada: {policy_name}')
    except iam.exceptions.EntityAlreadyExistsException:
        versions = iam.list_policy_versions(PolicyArn=policy_arn)['Versions']
        for v in versions:
            if not v['IsDefaultVersion']:
                iam.delete_policy_version(PolicyArn=policy_arn, VersionId=v['VersionId'])
        iam.create_policy_version(PolicyArn=policy_arn,
                                  PolicyDocument=json.dumps(policy_doc), SetAsDefault=True)
        print(f'  Policy atualizada: {policy_name}')

upsert_policy()
iam.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=policy_arn)
print('  Policies anexadas')
set_env('WPP_GATEWAY_ROLE_ARN', f'arn:aws:iam::{ACCOUNT_ID}:role/{ROLE_NAME}')

print('\n=== INFRA DE VOZ PRONTA ===')
print(f'  Sessions table : {SESSIONS_TABLE}')
print(f'  Media bucket   : {MEDIA_BUCKET}')
print(f'  Inbound topic  : {inbound_arn}')
print(f'  Streaming topic: {streaming_arn}')
print(f'  Role           : {ROLE_NAME}')
