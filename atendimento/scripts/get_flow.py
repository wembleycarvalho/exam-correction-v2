"""Dump flow content to a JSON file for analysis."""
import boto3, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import get_env

REGION = get_env('AWS_REGION', 'us-east-1')
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'
FLOW_ID = 'acd511ac-afee-403b-9436-aa52f2f744cc'

connect = boto3.client('connect', region_name=REGION)
resp = connect.describe_contact_flow(InstanceId=INSTANCE_ID, ContactFlowId=FLOW_ID)
content = json.loads(resp['ContactFlow']['Content'])

with open('output/flow_content.json', 'w') as f:
    json.dump(content, f, indent=2, default=str)
print(f'Flow saved to output/flow_content.json ({len(content.get("Actions",[]))} actions)')
