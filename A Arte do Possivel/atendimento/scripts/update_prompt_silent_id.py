"""
Prompt :7 - identificacao SILENCIOSA. Base = :4. Troca o bloco INICIO DE CADA CONVERSA
para o bot identificar sem anunciar e sem re-cumprimentar a cada mensagem (cada msg e um
contato novo). Reaponta o agent 69d86b4f.

Uso: source .env && python3 scripts/update_prompt_silent_id.py
"""
import boto3, json, os, datetime, subprocess, tempfile

q = boto3.client('qconnect', region_name='us-east-1')
ASSISTANT = '4c588966-3671-4170-b53d-a6115502e9d1'
PROMPT = '3d787af2-0d57-4bd8-b8fa-ea2210a775ba'
AGENT = '69d86b4f-bb2e-4984-b4a1-570062837755'
BASE = '4'

OLD = """INICIO DE CADA CONVERSA:
    1. Use a tool connect_GetContactAttributes para obter o atributo "phone" do contato atual usando o contactId disponivel em system_variables.
    2. Com o telefone obtido, use a tool consultar_usuario para identificar o cliente.
    3. Se o usuario for cadastrado, chame-o pelo nome. Exemplo: "Ola, Wembley! Como posso ajudar?"
    4. Se NAO for cadastrado, pergunte educadamente o nome dele e ofereca informacoes sobre cursos disponiveis.
    5. NUNCA pergunte o telefone ao cliente."""

NEW = """IDENTIFICACAO (SILENCIOSA - CRITICO):
    1. Use connect_GetContactAttributes para obter o "phone" e depois consultar_usuario para saber quem e o cliente. Faca isso SILENCIOSAMENTE, sem anunciar.
    2. NUNCA diga "vou te identificar", "deixe-me identificar", "identifiquei voce", nem cumprimente com "Ola, [nome]! Como posso ajudar?". Cada mensagem faz parte de uma conversa em andamento no WhatsApp - o cliente NAO quer ser cumprimentado/identificado de novo a cada mensagem.
    3. Responda DIRETAMENTE o que o cliente pediu, ja usando os dados dele. Pode usar o primeiro nome naturalmente dentro da resposta, mas SEM saudacao ou apresentacao repetida.
    4. Se o cliente NAO for cadastrado (consultar_usuario nao encontrar), ai sim pergunte o nome e ofereca informacoes de cursos. NUNCA pergunte o telefone."""

p = q.get_ai_prompt(assistantId=ASSISTANT, aiPromptId=f'{PROMPT}:{BASE}')['aiPrompt']
txt = p['templateConfiguration']['textFullAIPromptEditTemplateConfiguration']['text']
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bdir = os.path.join('backups', f'prompt_{ts}'); os.makedirs(bdir, exist_ok=True)
open(os.path.join(bdir, f'prompt_v{BASE}.txt'), 'w').write(txt)
if OLD not in txt:
    raise SystemExit('bloco INICIO nao encontrado - abortando (verifique o texto do :4)')
new_txt = txt.replace(OLD, NEW, 1)
open(os.path.join(bdir, 'prompt_new.txt'), 'w').write(new_txt)

q.update_ai_prompt(assistantId=ASSISTANT, aiPromptId=PROMPT, visibilityStatus='PUBLISHED',
                   templateConfiguration={'textFullAIPromptEditTemplateConfiguration': {'text': new_txt}})
ver = q.create_ai_prompt_version(assistantId=ASSISTANT, aiPromptId=PROMPT)
vnum = ver.get('versionNumber') or ver.get('aiPrompt', {}).get('versionNumber')
print(f'nova versao: {PROMPT}:{vnum} (backup {bdir})')

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
print('ROLLBACK: python3 scripts/repoint_agent_prompt.py 4')
