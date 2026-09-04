"""
Provisiona, POR TEMPLATE (nao depende de aprovacao Meta):
  - pasta S3        campanhas/<slug>/
  - object type     Campaign-<slug>   (phone chave + varN -> Attributes.varN)
  - event trigger   trigger-<slug>

A campanha em si so nasce quando o template for APPROVED (scripts/campaign_setup.py).

Uso:
  source .env && python3 scripts/setup_campaign_templates.py            # todos os templates
  source .env && python3 scripts/setup_campaign_templates.py --template confirmacao_recebida
"""
import argparse
import os
import sys
import boto3

sys.path.insert(0, os.path.dirname(__file__))
import campaign_lib as lib

REGION = os.environ.get('AWS_REGION', 'us-east-1')
ACCOUNT = os.environ.get('AWS_ACCOUNT_ID', '123456789012')
WABA_ID = os.environ.get('WABA_ID', 'waba-b7e8aaaa528c4a73a9dc4212f4323c79')
BUCKET = os.environ.get('CAMPAIGN_BUCKET', f'campanhas-connect-{ACCOUNT}')

sm = boto3.client('socialmessaging', region_name=REGION)
cp = boto3.client('customer-profiles', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)


def provision(name, meta_id):
    _, _, cols, _ = lib.template_columns(sm, WABA_ID, meta_id)
    folder = lib.ensure_s3_folder(s3, BUCKET, name)
    otn = lib.ensure_object_type(cp, name, cols)
    tname = lib.ensure_event_trigger(cp, name)
    print(f'  [{name}]')
    print(f'    pasta S3     : s3://{BUCKET}/{folder}')
    print(f'    object type  : {otn}  (colunas: {",".join(cols)})')
    print(f'    event trigger: {tname}')


def main(only):
    tpls = sm.list_whatsapp_message_templates(id=WABA_ID).get('templates', [])
    if only:
        tpls = [t for t in tpls if t.get('templateName') == only]
        if not tpls:
            raise SystemExit(f'template "{only}" nao encontrado na WABA')
    print(f'Provisionando {len(tpls)} template(s) no bucket {BUCKET}:')
    for t in tpls:
        provision(t['templateName'], t['metaTemplateId'])
    print('\nOK. Pastas + object types + triggers prontos. '
          'A campanha de cada template nasce na aprovacao (campaign_setup.py).')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--template', help='nome do template (default: todos)')
    a = ap.parse_args()
    main(a.template)
