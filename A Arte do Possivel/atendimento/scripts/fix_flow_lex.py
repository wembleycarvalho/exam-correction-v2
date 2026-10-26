"""Fix flow to use new Lex bot."""
import boto3, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import get_env

REGION = get_env('AWS_REGION', 'us-east-1')
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
FLOW_ID = 'acd511ac-afee-403b-9436-aa52f2f744cc'

connect = boto3.client('connect', region_name=REGION)
flow_resp = connect.describe_contact_flow(InstanceId=INSTANCE_ID, ContactFlowId=FLOW_ID)
content_str = flow_resp['ContactFlow']['Content']

# Replace old Lex bot with new
old_lex = 'KS8ONTST78'
new_lex = 'IIGUGVMZDL'

if old_lex in content_str:
    content_str = content_str.replace(old_lex, new_lex)
    content_str = content_str.replace('connect-demo-conv-ai', 'bot-nova')
    print(f'Lex bot atualizado: {old_lex} -> {new_lex}')
elif new_lex in content_str:
    print(f'Lex bot ja esta correto: {new_lex}')
else:
    print('WARN: Nenhum Lex bot encontrado no fluxo')

connect.update_contact_flow_content(
    InstanceId=INSTANCE_ID,
    ContactFlowId=FLOW_ID,
    Content=content_str
)
print('Fluxo salvo!')
