# Lambda: connect-harness-integration
# Runtime: python3.12 | Timeout: 120s | Memory: 256MB
# Role: ConnectHarnessLambdaRole
# Layers: boto3-latest
# Env vars: ASYNC_FUNCTION_NAME
"""
Lambda sincrona (chamada pelo Connect) - responde rapido e
invoca a Lambda async para processar com o harness.
"""
import json
import os
import boto3

ASYNC_FUNCTION = os.environ.get('ASYNC_FUNCTION_NAME', 'connect-harness-async')
REGION = os.environ.get('AWS_REGION', 'us-east-1')


def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")

    details = event.get('Details', {})
    contact_data = details.get('ContactData', {})
    customer_endpoint = contact_data.get('CustomerEndpoint', {})
    phone = customer_endpoint.get('Address', '')
    contact_id = contact_data.get('ContactId', '')

    lmb = boto3.client('lambda', region_name=REGION)
    lmb.invoke(
        FunctionName=ASYNC_FUNCTION,
        InvocationType='Event',
        Payload=json.dumps({'phone': phone, 'contactId': contact_id})
    )

    return {'response': 'Estamos analisando e ja retorno.'}
