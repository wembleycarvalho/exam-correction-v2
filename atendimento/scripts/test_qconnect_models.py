"""Test which models Q Connect supports."""
import boto3
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import get_env

REGION = get_env('AWS_REGION', 'us-east-1')
ASSISTANT_ID = get_env('ASSISTANT_ID', '8a30d6b7-c8db-420e-b8af-8f8bf75f2dc3')
qconnect = boto3.client('qconnect', region_name=REGION)

models = [
    'anthropic.claude-3-haiku-20240307-v1:0',
    'anthropic.claude-3-5-haiku-20241022-v1:0',
    'amazon.nova-lite-v1:0',
    'amazon.nova-micro-v1:0',
    'amazon.nova-pro-v1:0',
]

for m in models:
    try:
        resp = qconnect.create_ai_prompt(
            assistantId=ASSISTANT_ID,
            name=f'test-model',
            type='ANSWER_GENERATION',
            templateType='TEXT',
            visibilityStatus='PUBLISHED',
            apiFormat='MESSAGES',
            modelId=m,
            templateConfiguration={
                'textFullAIPromptEditTemplateConfiguration': {
                    'text': 'test $.contentExcerpt $.queryText'
                }
            },
        )
        pid = resp['aiPrompt']['aiPromptId']
        print(f'SUPPORTED: {m} -> {pid}')
        qconnect.delete_ai_prompt(assistantId=ASSISTANT_ID, aiPromptId=pid)
        break
    except Exception as e:
        err = str(e)
        if 'not supported' in err.lower():
            print(f'NOT SUPPORTED: {m}')
        elif 'Conflict' in err:
            print(f'CONFLICT: {m} (name in use)')
            # delete and retry
            prompts = qconnect.list_ai_prompts(assistantId=ASSISTANT_ID)
            for p in prompts.get('aiPromptSummaries', []):
                if p['name'] == 'test-model':
                    qconnect.delete_ai_prompt(assistantId=ASSISTANT_ID, aiPromptId=p['aiPromptId'])
                    print(f'  Deleted old test prompt')
                    break
        else:
            print(f'ERROR: {m} -> {err[:150]}')
