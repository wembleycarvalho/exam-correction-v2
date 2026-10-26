"""
Finaliza a remocao do CloudFront do 3P app abandonado (Agent Briefing App).
O CloudFront precisa estar DISABLED e com status Deployed antes de deletar.
Roda em loop ate conseguir deletar a distribution e o OAC.

Uso: source .env && python3 scripts/cleanup_cloudfront.py
"""
import boto3
import time
import sys

cf = boto3.client('cloudfront', region_name='us-east-1')
DIST = 'E1F0DC04882DPQ'

print(f'Finalizando remocao do CloudFront {DIST}...')

for attempt in range(20):
    try:
        resp = cf.get_distribution(Id=DIST)
    except cf.exceptions.NoSuchDistribution:
        print('Distribution ja deletada.')
        break
    status = resp['Distribution']['Status']
    enabled = resp['Distribution']['DistributionConfig']['Enabled']
    etag = resp['ETag']
    print(f'  Tentativa {attempt+1}: status={status} enabled={enabled}')

    if not enabled and status == 'Deployed':
        try:
            cf.delete_distribution(Id=DIST, IfMatch=etag)
            print('  CloudFront DELETADO!')
            break
        except Exception as e:
            print(f'  Erro ao deletar: {e}')
    time.sleep(60)
else:
    print('Timeout. Rode novamente mais tarde para concluir a delecao.')
    sys.exit(0)

# Delete OAC
try:
    oacs = cf.list_origin_access_controls().get('OriginAccessControlList', {}).get('Items', [])
    for oac in oacs:
        if 'agent-briefing' in oac.get('Name', ''):
            o = cf.get_origin_access_control(Id=oac['Id'])
            cf.delete_origin_access_control(Id=oac['Id'], IfMatch=o['ETag'])
            print(f'  OAC deletado: {oac["Name"]}')
except Exception as e:
    print(f'  OAC: {e}')

print('Cleanup do CloudFront concluido.')
