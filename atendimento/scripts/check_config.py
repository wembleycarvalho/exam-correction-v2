"""Check current config."""
import boto3, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import get_env

REGION = get_env('AWS_REGION', 'us-east-1')
qconnect = boto3.client('qconnect', region_name=REGION)
connect = boto3.client('connect', region_name=REGION)
aid = '4c588966-3671-4170-b53d-a6115502e9d1'

# Assistant config
resp = qconnect.get_assistant(assistantId=aid)
config = resp['assistant'].get('aiAgentConfiguration', {})
print('=== Default AI Agent Configurations ===')
for k, v in config.items():
    print(f'  {k}: {v}')

# Check copiloto-atendente
print('\n=== copiloto-atendente ===')
agent_id = '69d86b4f-bb2e-4984-b4a1-570062837755'
detail = qconnect.get_ai_agent(assistantId=aid, aiAgentId=agent_id)
orch = detail['aiAgent']['configuration'].get('orchestrationAIAgentConfiguration', {})
print(f'  Prompt: {orch.get("orchestrationAIPromptId", "N/A")}')
print(f'  Tools: {len(orch.get("toolConfigurations", []))}')
for t in orch.get('toolConfigurations', []):
    print(f'    {t["toolName"]}')

# Check flow
print('\n=== Flow ===')
flow = connect.describe_contact_flow(InstanceId='82a1c25d-b923-4bd2-9c21-e7eba7f052ac', ContactFlowId='acd511ac-afee-403b-9436-aa52f2f744cc')
content = flow['ContactFlow']['Content']
if '69d86b4f' in content:
    print('  Flow uses copiloto-atendente as self-service')
if '9fe5ed34' in content:
    print('  Flow uses agent-nova as self-service')
# Find the AI agent ARN in the flow
import re
arns = re.findall(r'ai-agent/[^"]+', content)
print(f'  AI Agent ARNs in flow: {arns}')
