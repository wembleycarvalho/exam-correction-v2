"""
Lista registros de memoria do AgentCore.
Uso: source .env && python3 list_memory.py [tipo]
Tipos: episodic, preference, semantic, summarization
"""
import boto3
import json
import sys
import os

REGION = os.environ.get('AWS_REGION', 'us-east-1')
MEMORY_ID = os.environ.get('HARNESS_MEMORY_ARN', '').split('/')[-1]

if not MEMORY_ID:
    print('HARNESS_MEMORY_ARN not set in .env')
    sys.exit(1)

client = boto3.client('bedrock-agentcore', region_name=REGION)

# Get memory config to find strategies
ctrl = boto3.client('bedrock-agentcore-control', region_name=REGION)
memory = ctrl.get_memory(memoryId=MEMORY_ID)['memory']

filter_type = sys.argv[1].upper() if len(sys.argv) > 1 else None
total = 0

for strategy in memory.get('strategies', []):
    stype = strategy.get('type', '')
    sid = strategy['strategyId']
    if filter_type and filter_type not in stype:
        continue

    path = f'/strategies/{sid}/'
    print(f'\n{"="*60}')
    print(f' {stype} ({sid})')
    print(f'{"="*60}')

    try:
        next_token = None
        count = 0
        while True:
            params = {'memoryId': MEMORY_ID, 'namespacePath': path}
            if next_token:
                params['nextToken'] = next_token
            resp = client.list_memory_records(**params)
            records = resp.get('memoryRecordSummaries', [])
            count += len(records)
            for r in records:
                print(json.dumps(r, indent=2, default=str))
                print('---')
            next_token = resp.get('nextToken')
            if not next_token:
                break
        print(f'  Total: {count} records')
        total += count
    except Exception as e:
        print(f'  Error: {e}')

print(f'\n{"="*60}')
print(f' TOTAL: {total} records')
print(f'{"="*60}')
