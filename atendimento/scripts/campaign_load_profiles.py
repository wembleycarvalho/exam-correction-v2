"""
Disparo EXTERNO nativo (fiel ao CSV) para UM template: sobe o CSV na pasta do template
(campanhas/<slug>/) e escreve 1 objeto de perfil do tipo Campaign-<slug> por linha. Cada
objeto gera um evento que dispara o event trigger daquele template -> sua campanha.

CSV: coluna 'phone' obrigatoria + colunas mapeadas no object type (var1, var2, ...).

Uso:
  source .env && python3 scripts/campaign_load_profiles.py --template confirmacao_recebida arquivo.csv
  (--dry mostra o que faria sem gravar)
"""
import argparse
import csv
import json
import os
import sys
import datetime
import boto3

sys.path.insert(0, os.path.dirname(__file__))
import campaign_lib as lib

REGION = os.environ.get('AWS_REGION', 'us-east-1')
ACCOUNT = os.environ.get('AWS_ACCOUNT_ID', '123456789012')
BUCKET = os.environ.get('CAMPAIGN_BUCKET', f'campanhas-connect-{ACCOUNT}')

cp = boto3.client('customer-profiles', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)
sm = boto3.client('socialmessaging', region_name=REGION)
q = boto3.client('qconnect', region_name=REGION)
cc = boto3.client('connectcampaignsv2', region_name=REGION)
connect = boto3.client('connect', region_name=REGION)


def _obj(row):
    phone = (row.get('phone') or row.get('Phone') or '').strip()
    if not phone:
        return None
    if not phone.startswith('+'):
        phone = '+' + phone
    obj = {'phone': phone}
    for k, v in row.items():
        if k and k.strip().lower() != 'phone' and v and v.strip():
            obj[k.strip()] = v.strip()
    return obj


def _meta_id(template):
    for t in sm.list_whatsapp_message_templates(id=lib.WABA_ID).get('templates', []):
        if t.get('templateName') == template:
            return t.get('metaTemplateId')
    return None


def main(template, path, dry, label=None):
    label = label or template
    otn = lib.object_type_name(template)
    folder = lib.s3_folder(template)
    with open(path, newline='', encoding='utf-8') as f:
        text = f.read()
    rows = list(csv.DictReader(text.splitlines()))
    print(f'{len(rows)} linha(s) | template: {template} | object type: {otn}{" (DRY)" if dry else ""}')

    if not dry:
        stamp = datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        key = f'{folder}{stamp}-{os.path.basename(path)}'
        s3.put_object(Bucket=BUCKET, Key=key, Body=text.encode('utf-8'), ContentType='text/csv')
        print(f'CSV no S3: s3://{BUCKET}/{key}')

    ok, phones = 0, []
    for i, row in enumerate(rows, 1):
        obj = _obj(row)
        if not obj:
            print(f'  [{i}] sem phone')
            continue
        if dry:
            print(f'  [{i}] DRY {obj}')
            ok += 1
            if obj['phone'] not in phones:
                phones.append(obj['phone'])
            continue
        try:
            cp.put_profile_object(DomainName=lib.CP_DOMAIN, ObjectTypeName=otn,
                                  Object=json.dumps(obj))
            print(f'  [{i}] perfil gravado ({obj["phone"]})')
            ok += 1
            if obj['phone'] not in phones:
                phones.append(obj['phone'])
        except Exception as e:
            print(f'  [{i}] ERRO: {e}')

    print(f'\n{ok}/{len(rows)} perfil(s) processado(s); {len(phones)} destinatario(s).')
    if dry:
        print('(dry-run) - campanha nao criada.')
        return
    meta_id = _meta_id(template)
    res = lib.dispatch_campaign(sm, q, cc, connect, cp, template, meta_id, phones, label=label)
    print('Campanha nativa (nova por disparo):')
    print(f'  status       : {res.get("status")}')
    print(f'  campanha     : {res.get("campaignName")}')
    print(f'  campaignId   : {res.get("campaignId")}')
    print(f'  message tpl  : {res.get("wisdomArn")}')
    print(f'  flow         : {res.get("flowArn")}')
    print(f'  segmento     : {res.get("segmentArn")}')
    print('A campanha dispara na janela do schedule (~5-6 min apos a criacao).')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('csv')
    ap.add_argument('--template', required=True, help='nome do template WhatsApp da campanha')
    ap.add_argument('--name', help='rotulo da campanha (data/hora e adicionada automaticamente)')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    main(a.template, a.csv, a.dry, a.name)
