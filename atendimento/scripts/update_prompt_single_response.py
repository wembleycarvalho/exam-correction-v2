"""
Cria versao nova do prompt (base = :4) que evita mensagens intermediarias de progresso
(causa das respostas em DOBRO no WhatsApp) e reaponta o agent 69d86b4f.
Troca a regra "sempre iniciar com <message> mesmo ao usar tools" por "responder UMA vez".

Uso: source .env && python3 scripts/update_prompt_single_response.py
"""
import boto3, json, os, datetime, subprocess, tempfile

q = boto3.client('qconnect', region_name='us-east-1')
ASSISTANT = '4c588966-3671-4170-b53d-a6115502e9d1'
PROMPT = '3d787af2-0d57-4bd8-b8fa-ea2210a775ba'
AGENT = '69d86b4f-bb2e-4984-b4a1-570062837755'
BASE_VERSION = '4'

OLD = "MUST always start with `<message>` tags, even when using tools, to let the customer know you are working to resolve their issue."
NEW = ("MUST respond only ONCE per customer message, with a SINGLE `<message>` containing the "
       "complete final answer. When you need tools, call them SILENTLY (no message) and reply only "
       "after you have the result. NEVER send intermediate/progress messages such as 'deixe-me "
       "verificar', 'um momento', 'vou buscar' or 'recebi a imagem' - go straight to the final answer.")

p = q.get_ai_prompt(assistantId=ASSISTANT, aiPromptId=f'{PROMPT}:{BASE_VERSION}')['aiPrompt']
txt = p['templateConfiguration']['textFullAIPromptEditTemplateConfiguration']['text']
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bdir = os.path.join('backups', f'prompt_{ts}'); os.makedirs(bdir, exist_ok=True)
open(os.path.join(bdir, f'prompt_v{BASE_VERSION}.txt'), 'w').write(txt)

if OLD not in txt:
    raise SystemExit('linha de formatting nao encontrada - abortando (verifique o texto)')
new_txt = txt.replace(OLD, NEW, 1)
open(os.path.join(bdir, 'prompt_new.txt'), 'w').write(new_txt)

q.update_ai_prompt(assistantId=ASSISTANT, aiPromptId=PROMPT, visibilityStatus='PUBLISHED',
                   templateConfiguration={'textFullAIPromptEditTemplateConfiguration': {'text': new_txt}})
ver = q.create_ai_prompt_version(assistantId=ASSISTANT, aiPromptId=PROMPT)
vnum = ver.get('versionNumber') or ver.get('aiPrompt', {}).get('versionNumber')
print(f'nova versao: {PROMPT}:{vnum} (backup {bdir})')

# repoint
agent = q.get_ai_agent(assistantId=ASSISTANT, aiAgentId=AGENT)['aiAgent']
orch = agent['configuration']['orchestrationAIAgentConfiguration']
MCP = {'toolName', 'toolType', 'toolId', 'overrideInputValues', 'userInteractionConfiguration'}
def clean(t):
    if t.get('toolType') == 'MODEL_CONTEXT_PROTOCOL':
        return {k: v for k, v in t.items() if k in MCP}
    return {k: t[k] for k in ['toolName','toolType','toolId','description','instruction','inputSchema','userInteractionConfiguration'] if k in t and t[k] is not None}
config = {'orchestrationAIAgentConfiguration': {
    'orchestrationAIPromptId': f'{PROMPT}:{vnum}',
    'connectInstanceArn': orch['connectInstanceArn'],
    'locale': orch.get('locale', 'pt_BR'),
    'toolConfigurations': [clean(t) for t in orch.get('toolConfigurations', [])]}}
tf = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False); json.dump(config, tf); tf.close()
r = subprocess.run(['aws','qconnect','update-ai-agent','--assistant-id',ASSISTANT,'--ai-agent-id',AGENT,
                    '--visibility-status','PUBLISHED','--configuration',f'file://{tf.name}','--region','us-east-1'],
                   capture_output=True, text=True)
os.unlink(tf.name)
print('repoint rc:', r.returncode, r.stderr[:300] if r.returncode else '')
a2 = q.get_ai_agent(assistantId=ASSISTANT, aiAgentId=AGENT)['aiAgent']
print('agent aponta:', a2['configuration']['orchestrationAIAgentConfiguration']['orchestrationAIPromptId'])
print('ROLLBACK: python3 scripts/repoint_agent_prompt.py 4')
