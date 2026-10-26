"""
Tester CLI de templates WhatsApp (AWS End User Messaging Social). Funciona em qualquer
ambiente (nao serve porta local). Lista status e dispara envio 1-a-1.

Listar status:
  source .env && python3 scripts/send_template_test.py --list

Enviar template de teste (variaveis do corpo em ordem {{1}},{{2}}...):
  source .env && python3 scripts/send_template_test.py \
      --to +5511985743177 --template aviso_mensalidade --lang pt_BR --vars "Wembley,Junho/2026"
"""
import argparse
import json
import os
import boto3

REGION = os.environ.get('AWS_REGION', 'us-east-1')
WABA_ID = os.environ.get('WABA_ID', 'waba-b7e8aaaa528c4a73a9dc4212f4323c79')
ORIGIN = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', 'phone-number-id-fe268d418d9b4e1296c47f86795987df')
META_API = os.environ.get('META_API_VERSION', 'v20.0')

sm = boto3.client('socialmessaging', region_name=REGION)

C = {'APPROVED': '\033[92m', 'PENDING': '\033[93m', 'REJECTED': '\033[91m', '_': '\033[0m'}


def listar():
    r = sm.list_whatsapp_message_templates(id=WABA_ID)
    print('\nTemplates da WABA:')
    for t in r.get('templates', []):
        st = t.get('templateStatus', '?')
        col = C.get(st, '')
        print(f"  {col}{st:9}{C['_']} | {t.get('templateName'):22} | "
              f"{t.get('templateCategory'):12} | {t.get('templateLanguage')}")
    print()


def enviar(to, template, lang, varlist):
    if not to.startswith('+'):
        to = '+' + to
    comps = []
    if varlist:
        comps = [{'type': 'body', 'parameters': [{'type': 'text', 'text': v} for v in varlist]}]
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': to,
        'type': 'template',
        'template': {'name': template, 'language': {'code': lang}, 'components': comps},
    }
    print(f'enviando "{template}" ({lang}) -> {to}  vars={varlist}')
    try:
        resp = sm.send_whatsapp_message(
            originationPhoneNumberId=ORIGIN,
            message=json.dumps(payload).encode('utf-8'),
            metaApiVersion=META_API)
        print(f"  OK! messageId: {resp.get('messageId')}")
    except Exception as e:
        print(f"  ERRO: {e}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--to')
    ap.add_argument('--template')
    ap.add_argument('--lang', default='pt_BR')
    ap.add_argument('--vars', default='', help='valores das variaveis separados por virgula')
    a = ap.parse_args()
    if a.list or not a.template:
        listar()
    else:
        varlist = [v.strip() for v in a.vars.split(',') if v.strip()] if a.vars else []
        if not a.to:
            print('informe --to +DDI...')
        else:
            enviar(a.to, a.template, a.lang, varlist)
