"""
Reaponta o AI agent 69d86b4f (usado pelo fluxo) para uma versao do prompt wembley-prompt.
Reenvia toolConfigurations com o tratamento correto (steering connect-licoes-aprendidas):
  - MCP (MODEL_CONTEXT_PROTOCOL): apenas toolName, toolType, toolId, overrideInputValues,
    userInteractionConfiguration (NAO reenviar inputSchema/description).
  - RETURN_TO_CONTROL (Complete/Escalate): reenvia completo (instruction, inputSchema, ...).
Usa AWS CLI (boto3 pode nao suportar orchestrationAIAgentConfiguration).

Uso:
  source .env && python3 scripts/repoint_agent_prompt.py 3     # aponta para :3 (fix)
  source .env && python3 scripts/repoint_agent_prompt.py 1     # ROLLBACK para :1
"""
import boto3, json, os, sys, subprocess, tempfile

q = boto3.client('qconnect', region_name='us-east-1')
ASSISTANT = '4c588966-3671-4170-b53d-a6115502e9d1'
AGENT = '69d86b4f-bb2e-4984-b4a1-570062837755'
PROMPT = '3d787af2-0d57-4bd8-b8fa-ea2210a775ba'

version = sys.argv[1] if len(sys.argv) > 1 else None
if not version:
    raise SystemExit('informe a versao alvo. Ex: python3 scripts/repoint_agent_prompt.py 3')

agent = q.get_ai_agent(assistantId=ASSISTANT, aiAgentId=AGENT)['aiAgent']
orch = agent['configuration']['orchestrationAIAgentConfiguration']

MCP_ALLOWED = {'toolName', 'toolType', 'toolId', 'overrideInputValues', 'userInteractionConfiguration'}

def clean_tool(t):
    if t.get('toolType') == 'MODEL_CONTEXT_PROTOCOL':
        return {k: v for k, v in t.items() if k in MCP_ALLOWED}
    # RETURN_TO_CONTROL: reenvia campos relevantes (sem toolId None)
    out = {}
    for k in ['toolName', 'toolType', 'toolId', 'description', 'instruction',
              'inputSchema', 'userInteractionConfiguration']:
        if k in t and t[k] is not None:
            out[k] = t[k]
    return out

tools = [clean_tool(t) for t in orch.get('toolConfigurations', [])]

config = {
    'orchestrationAIAgentConfiguration': {
        'orchestrationAIPromptId': f'{PROMPT}:{version}',
        'connectInstanceArn': orch['connectInstanceArn'],
        'locale': orch.get('locale', 'pt_BR'),
        'toolConfigurations': tools,
    }
}

tmp = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
json.dump(config, tmp, ensure_ascii=False)
tmp.close()
print(f'apontando agent {AGENT} -> prompt {PROMPT}:{version}')
print(f'  tools reenviadas: {len(tools)}')

cmd = ['aws', 'qconnect', 'update-ai-agent',
       '--assistant-id', ASSISTANT, '--ai-agent-id', AGENT,
       '--visibility-status', 'PUBLISHED',
       '--configuration', f'file://{tmp.name}',
       '--region', 'us-east-1']
r = subprocess.run(cmd, capture_output=True, text=True)
print('returncode:', r.returncode)
if r.returncode != 0:
    print('STDERR:', r.stderr[:1500])
    os.unlink(tmp.name)
    raise SystemExit('update-ai-agent FALHOU')
os.unlink(tmp.name)

# verifica
a2 = q.get_ai_agent(assistantId=ASSISTANT, aiAgentId=AGENT)['aiAgent']
o2 = a2['configuration']['orchestrationAIAgentConfiguration']
print('agora promptId:', o2.get('orchestrationAIPromptId'))
print('tools apos update:', len(o2.get('toolConfigurations', [])))
for t in o2.get('toolConfigurations', []):
    print('   -', t.get('toolName'), '|', t.get('toolType'))
print('\nOK.')
