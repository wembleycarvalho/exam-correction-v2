"""
Etapa 1 (NAO-destrutiva): cria uma versao NOVA do prompt wembley-prompt (3d787af2)
com a regra ENTREGA DE INFORMACAO (entregar em vez de prometer + responder tudo na
1a mensagem + tratar 'por texto/email' so como formato). NAO repoenta o agent ainda.

Backups salvos em backups/prompt_<ts>/ (texto da :1 + config do agent 69d86b4f).

Uso: source .env && python3 scripts/update_prompt_deliver.py
"""
import boto3, json, os, datetime

q = boto3.client('qconnect', region_name='us-east-1')
ASSISTANT = '4c588966-3671-4170-b53d-a6115502e9d1'
PROMPT = '3d787af2-0d57-4bd8-b8fa-ea2210a775ba'
AGENT = '69d86b4f-bb2e-4984-b4a1-570062837755'

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bdir = os.path.join('backups', f'prompt_{ts}')
os.makedirs(bdir, exist_ok=True)

# 1. Backup da versao :1 (texto) e da config do agent
p = q.get_ai_prompt(assistantId=ASSISTANT, aiPromptId=PROMPT + ':1')['aiPrompt']
txt = p['templateConfiguration']['textFullAIPromptEditTemplateConfiguration']['text']
with open(os.path.join(bdir, 'prompt_v1.txt'), 'w') as f:
    f.write(txt)
agent = q.get_ai_agent(assistantId=ASSISTANT, aiAgentId=AGENT)['aiAgent']
with open(os.path.join(bdir, 'agent_config_BEFORE.json'), 'w') as f:
    json.dump(agent, f, indent=2, default=str, ensure_ascii=False)
print(f'backup salvo em {bdir}/ (prompt_v1.txt, agent_config_BEFORE.json)')

# 2. Inserir a regra ENTREGA logo apos "REGRAS ESPECIFICAS DO NEGOCIO:"
REGRA = """REGRAS ESPECIFICAS DO NEGOCIO:
    ENTREGA DE INFORMACAO (CRITICO):
    - Voce se comunica APENAS por esta conversa (WhatsApp). NUNCA diga que vai "enviar", "mandar por email", "mandar depois" ou "ja estou enviando" uma informacao - voce NAO tem outro canal. SEMPRE inclua a informacao pedida DIRETAMENTE na sua resposta.
    - Se o cliente pedir para receber algo "por texto", "por escrito", "por audio" ou "por email", trate APENAS como preferencia de formato e responda normalmente com o conteudo na propria mensagem.
    - SEMPRE chame a tool apropriada e ESPERE o resultado ANTES de responder (ex: consultar_academico com tipo_consulta=prova para provas). Baseie a resposta no resultado da tool. NUNCA prometa buscar depois nem invente conteudo.
    - Na PRIMEIRA mensagem, alem de cumprimentar, ja responda o que o cliente pediu (depois de chamar as tools). NUNCA responda so com uma saudacao quando o cliente ja fez um pedido.
    - EXCECAO: a tool gerar_boleto realmente envia um documento no WhatsApp; so nesse caso voce pode dizer que enviou o boleto."""

anchor = "REGRAS ESPECIFICAS DO NEGOCIO:"
if anchor not in txt:
    raise SystemExit('ancora nao encontrada no prompt - abortando')
if 'ENTREGA DE INFORMACAO' in txt:
    raise SystemExit('regra ENTREGA ja presente - nada a fazer')
new_txt = txt.replace(anchor, REGRA, 1)
with open(os.path.join(bdir, 'prompt_v_new.txt'), 'w') as f:
    f.write(new_txt)
print(f'novo texto gerado (len {len(new_txt)} vs {len(txt)})')

# 3. update_ai_prompt (working copy) + create_ai_prompt_version
q.update_ai_prompt(
    assistantId=ASSISTANT,
    aiPromptId=PROMPT,
    visibilityStatus='PUBLISHED',
    templateConfiguration={'textFullAIPromptEditTemplateConfiguration': {'text': new_txt}},
)
print('update_ai_prompt OK (working copy atualizada)')

ver = q.create_ai_prompt_version(assistantId=ASSISTANT, aiPromptId=PROMPT)
vnum = ver['aiPrompt']['version'] if 'version' in ver.get('aiPrompt', {}) else ver.get('versionNumber')
# fallback: alguns SDKs retornam em modifiedTime; tentar varios
vnum = (ver.get('versionNumber')
        or ver.get('aiPrompt', {}).get('versionNumber')
        or ver.get('aiPrompt', {}).get('version'))
print('create_ai_prompt_version resp keys:', list(ver.keys()))
print('nova versao:', vnum)
with open(os.path.join(bdir, 'NEW_VERSION.txt'), 'w') as f:
    f.write(str(vnum))
print(f'\nETAPA 1 OK. Nova versao do prompt: {PROMPT}:{vnum}')
print(f'Agent 69d86b4f AINDA aponta para :1 (nada mudou no ar). Backup: {bdir}')
