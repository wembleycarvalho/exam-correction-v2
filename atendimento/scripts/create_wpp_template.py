"""
Cria um template de mensagem WhatsApp via AWS End User Messaging Social (a AWS envia
pra aprovacao da Meta). Uso:
  source .env && python3 scripts/create_wpp_template.py aviso_mensalidade
  source .env && python3 scripts/create_wpp_template.py vestibular

Depois, acompanhe a aprovacao: python3 scripts/create_wpp_template.py --list
"""
import boto3, json, os, sys

REGION = os.environ.get('AWS_REGION', 'us-east-1')
WABA_ID = os.environ.get('WABA_ID', 'waba-b7e8aaaa528c4a73a9dc4212f4323c79')
sm = boto3.client('socialmessaging', region_name=REGION)

TEMPLATES = {
    'aviso_mensalidade': {
        'name': 'aviso_mensalidade',
        'language': 'pt_BR',
        'category': 'UTILITY',
        'components': [
            {'type': 'BODY',
             'text': ('Ola, {{1}}! Passando para lembrar que sua mensalidade de {{2}} esta '
                      'disponivel. Se precisar da segunda via do boleto, e so responder esta '
                      'mensagem que eu te ajudo por aqui. :)'),
             'example': {'body_text': [['Wembley', 'Junho/2026']]}},
            {'type': 'FOOTER', 'text': 'Faculdade Nova Horizonte'},
        ],
    },
    'confirmacao': {
        'name': 'confirmacao_recebida',
        'language': 'pt_BR',
        'category': 'UTILITY',
        'components': [
            {'type': 'BODY',
             'text': ('Recebemos sua solicitacao. Seu numero de protocolo e {{1}}. '
                      'Em breve retornaremos com as atualizacoes.'),
             'example': {'body_text': [['2026-0827-0001']]}},
        ],
    },
    'vestibular': {
        'name': 'vestibular_2026_2',
        'language': 'pt_BR',
        'category': 'MARKETING',
        'components': [
            {'type': 'BODY',
             'text': ('Ola, {{1}}! As inscricoes do Vestibular 2026.2 da Faculdade Nova Horizonte '
                      'estao abertas, com bolsas e financiamento estudantil. Quer saber sobre os '
                      'cursos, datas e como se inscrever?'),
             'example': {'body_text': [['Wembley']]}},
            {'type': 'BUTTONS',
             'buttons': [{'type': 'QUICK_REPLY', 'text': 'Quero saber mais'}]},
        ],
    },
}


def create(key):
    tpl = TEMPLATES[key]
    resp = sm.create_whatsapp_message_template(
        id=WABA_ID,
        templateDefinition=json.dumps(tpl).encode('utf-8'),
    )
    print(f'template "{tpl["name"]}" enviado.')
    print('  metaTemplateId:', resp.get('metaTemplateId'))
    print('  templateStatus:', resp.get('templateStatus'))
    print('  category:', resp.get('category'))


def listar():
    r = sm.list_whatsapp_message_templates(id=WABA_ID)
    for t in r.get('templates', []):
        print(f"  {t.get('templateName')} | {t.get('templateStatus')} | {t.get('templateCategory')} | {t.get('templateLanguage')}")


if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else 'aviso_mensalidade'
    if arg == '--list':
        listar()
    elif arg in TEMPLATES:
        create(arg)
    else:
        print('template desconhecido. Opcoes:', list(TEMPLATES.keys()))
