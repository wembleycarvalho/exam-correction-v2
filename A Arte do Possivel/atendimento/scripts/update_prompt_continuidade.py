"""
Cria versao nova do prompt wembley-prompt (3d787af2) com DUAS regras e reaponta o agent:
  1. CONTINUIDADE: nunca encerrar a conversa / nao usar Complete por conta propria
     -> o fluxo nao desconecta -> contato persiste -> acaba a corrida de disconnect.
  2. ENTREGA: entregar a info na propria mensagem (nunca "vou enviar"); tratar
     "por texto/audio/email" so como formato; sempre chamar a tool e responder.
Base: versao :1 (known-good). Reaponta o agent 69d86b4f pra nova versao (AWS CLI,
tools MCP limpas / RETURN_TO_CONTROL completas).

Uso: source .env && python3 scripts/update_prompt_continuidade.py
"""
import boto3, json, os, datetime, subprocess, tempfile

q = boto3.client('qconnect', region_name='us-east-1')
ASSISTANT = '4c588966-3671-4170-b53d-a6115502e9d1'
PROMPT = '3d787af2-0d57-4bd8-b8fa-ea2210a775ba'
AGENT = '69d86b4f-bb2e-4984-b4a1-570062837755'

REGRA = """REGRAS ESPECIFICAS DO NEGOCIO:
    CONTINUIDADE DA CONVERSA (CRITICO):
    - NUNCA encerre a conversa nem use a ferramenta Complete por conta propria. Depois de responder, permaneca disponivel e aguarde a proxima mensagem do cliente. So use Complete se o cliente se despedir de forma explicita (ex: "tchau", "obrigado, era so isso", "pode encerrar").
    - Responda TODA mensagem do cliente com o conteudo pedido, mesmo que ja tenha respondido outras antes. A conversa continua ate o cliente se despedir.
    ENTREGA DE INFORMACAO (CRITICO):
    - Voce se comunica APENAS por esta conversa (WhatsApp). NUNCA diga que vai "enviar", "mandar por email", "mandar depois" ou "ja estou enviando" uma informacao - voce NAO tem outro canal. SEMPRE inclua a informacao pedida DIRETAMENTE na sua resposta.
    - Se o cliente pedir algo "por texto", "por escrito", "por audio" ou "por email", trate APENAS como preferencia de formato e responda normalmente com o conteudo na propria mensagem.
    - SEMPRE chame a tool apropriada e ESPERE o resultado ANTES de responder. NUNCA prometa buscar depois nem invente conteudo.
    - EXCECAO: a tool gerar_boleto realmente envia um documento no WhatsApp; so nesse caso voce pode dizer que enviou o boleto."""

# 1. base = versao :1
p = q.get_ai_prompt(assistantId=ASSISTANT, aiPromptId=PROMPT + ':1')['aiPrompt']
txt = p['templateConfiguration']['textFullAIPromptEditTemplateConfiguration']['text']
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bdir = os.path.join('backups', f'prompt_{ts}')
os.makedirs(bdir, exist_ok=True)
with open(os.path.join(bdir, 'prompt_v1.txt'), 'w') as f:
    f.write(txt)

anchor = "REGRAS ESPECIFICAS DO NEGOCIO:"
new_txt = txt.replace(anchor, REGRA, 1)
with open(os.path.join(bdir, 'prompt_new.txt'), 'w') as f:
    f.write(new_txt)

# 2. update working copy + create version
q.update_ai_prompt(assistantId=ASSISTANT, aiPromptId=PROMPT, visibilityStatus='PUBLISHED',
                   templateConfiguration={'textFullAIPromptEditTemplateConfiguration': {'text': new_txt}})
ver = q.create_ai_prompt_version(assistantId=ASSISTANT, aiPromptId=PROMPT)
vnum = ver.get('versionNumber') or ver.get('aiPrompt', {}).get('versionNumber')
print(f'nova versao do prompt: {PROMPT}:{vnum}  (backup em {bdir})')

# 3. repoint agent (tools limpas)
agent = q.get_ai_agent(assistantId=ASSISTANT, aiAgentId=AGENT)['aiAgent']
orch = agent['configuration']['orchestrationAIAgentConfiguration']
MCP_ALLOWED = {'toolName', 'toolType', 'toolId', 'overrideInputValues', 'userInteractionConfiguration'}
def clean(t):
    if t.get('toolType') == 'MODEL_CONTEXT_PROTOCOL':
        return {k: v for k, v in t.items() if k in MCP_ALLOWED}
    return {k: t[k] for k in ['toolName','toolType','toolId','description','instruction','inputSchema','userInteractionConfiguration'] if k in t and t[k] is not None}
config = {'orchestrationAIAgentConfiguration': {
    'orchestrationAIPromptId': f'{PROMPT}:{vnum}',
    'connectInstanceArn': orch['connectInstanceArn'],
    'locale': orch.get('locale', 'pt_BR'),
    'toolConfigurations': [clean(t) for t in orch.get('toolConfigurations', [])],
}}
tf = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False); json.dump(config, tf); tf.close()
r = subprocess.run(['aws','qconnect','update-ai-agent','--assistant-id',ASSISTANT,'--ai-agent-id',AGENT,
                    '--visibility-status','PUBLISHED','--configuration',f'file://{tf.name}','--region','us-east-1'],
                   capture_output=True, text=True)
os.unlink(tf.name)
print('repoint returncode:', r.returncode, r.stderr[:400] if r.returncode else '')
a2 = q.get_ai_agent(assistantId=ASSISTANT, aiAgentId=AGENT)['aiAgent']
print('agent agora aponta:', a2['configuration']['orchestrationAIAgentConfiguration']['orchestrationAIPromptId'])
print(f'\nROLLBACK: python3 scripts/repoint_agent_prompt.py 1')
