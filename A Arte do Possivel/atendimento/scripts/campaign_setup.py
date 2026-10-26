"""
Motor de campanha NATIVO (pronto para rodar quando o template WhatsApp aprovar).
Cria, para um template APROVADO:
  1. Message template do Connect (Q in Connect) espelhando os componentes do template WhatsApp
     -> vira o wisdomTemplateArn.
  2. Campanha nativa (connectcampaignsv2) em modo Customer event (source.eventTrigger no dominio
     do Customer Profiles), canal WhatsApp, agentless, apontando pro numero + o message template.

Disparo: escrever/atualizar perfis no Customer Profiles (scripts/campaign_load_profiles.py)
-> o evento de perfil dispara a campanha nativa -> o motor do Connect envia.

Uso:
  source .env && python3 scripts/campaign_setup.py --template confirmacao_recebida
  source .env && python3 scripts/campaign_setup.py --list-campaigns
"""
import argparse
import json
import os
import sys
import boto3

sys.path.insert(0, os.path.dirname(__file__))
import campaign_lib as lib

REGION = os.environ.get('AWS_REGION', 'us-east-1')
ACCOUNT = os.environ.get('AWS_ACCOUNT_ID', '123456789012')
WABA_ID = os.environ.get('WABA_ID', 'waba-b7e8aaaa528c4a73a9dc4212f4323c79')
BUCKET = os.environ.get('CAMPAIGN_BUCKET', f'campanhas-connect-{ACCOUNT}')
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'

# recursos ja existentes (confirmados)
KB_ID = '5ad83ec7-1668-4dd6-92d1-7ab9d5e807c5'  # KB MESSAGE_TEMPLATES do dominio
CP_DOMAIN = 'amazon-connect-connect-demo-ps'
CP_DOMAIN_ARN = f'arn:aws:profile:{REGION}:{ACCOUNT}:domains/{CP_DOMAIN}'
WPP_NUMBER_ARN = f'arn:aws:connect:{REGION}:{ACCOUNT}:phone-number/15646f7c-964b-40a5-9097-6432f82945f8'

sm = boto3.client('socialmessaging', region_name=REGION)
q = boto3.client('qconnect', region_name=REGION)
cc = boto3.client('connectcampaignsv2', region_name=REGION)


def _approved_template(name):
    for t in sm.list_whatsapp_message_templates(id=WABA_ID).get('templates', []):
        if t.get('templateName') == name:
            return t
    return None


def ensure_template_resources(name, meta_template_id):
    """Prepara os recursos REUSAVEIS do template (nao dependem do CSV):
    pasta S3 (auditoria) + object type (CSV->perfil) + message template (Wisdom, tagueado) +
    campaign flow (SendWhatsAppMessage apontando pro template ATUAL). A campanha em si nasce no
    disparo (HTML/loader) com a lista de telefones do CSV (source = segmento fiel ao CSV)."""
    cp = boto3.client('customer-profiles', region_name=REGION)
    s3 = boto3.client('s3', region_name=REGION)
    connect = boto3.client('connect', region_name=REGION)
    _, _, cols, _ = lib.template_columns(sm, WABA_ID, meta_template_id)
    if BUCKET:
        lib.ensure_s3_folder(s3, BUCKET, name)
    lib.ensure_object_type(cp, name, cols)
    lang = (_approved_template(name) or {}).get('templateLanguage', 'pt_BR')
    wisdom = lib.ensure_message_template(q, sm, name, meta_template_id, lang)
    flow = lib.ensure_campaign_flow(connect, name, wisdom)
    print(f'  pasta S3        : s3://{BUCKET}/{lib.s3_folder(name)}')
    print(f'  object type     : {lib.object_type_name(name)}  (colunas: {",".join(cols)})')
    print(f'  message template: {wisdom}')
    print(f'  campaign flow   : {flow}')
    return wisdom, flow


def setup(template_name):
    t = _approved_template(template_name)
    if not t:
        raise SystemExit(f'template "{template_name}" nao encontrado na WABA')
    if t.get('templateStatus') != 'APPROVED':
        raise SystemExit(f'template "{template_name}" esta {t.get("templateStatus")} - '
                         f'so da pra montar a campanha quando estiver APPROVED.')
    print(f'template APROVADO: {template_name} (meta {t.get("metaTemplateId")})')
    ensure_template_resources(template_name, t['metaTemplateId'])
    print('\nOK. Recursos reusaveis prontos (template + flow + object type).')
    print(f'Disparo (cria a campanha fiel ao CSV): '
          f'scripts/campaign_load_profiles.py --template {template_name} <csv> '
          '(ou a aba Campanha no HTML).')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--template', help='nome do template WhatsApp APROVADO')
    ap.add_argument('--list-campaigns', action='store_true')
    a = ap.parse_args()
    if a.list_campaigns:
        for c in cc.list_campaigns().get('campaignSummaryList', []):
            print(f"  {c.get('name')} | {c.get('id')}")
    elif a.template:
        setup(a.template)
    else:
        ap.print_help()
