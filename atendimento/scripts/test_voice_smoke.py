"""
Smoke test da migracao de voz (SEM celular). Valida na infra REAL:
  1. Runtime/import health das duas Lambdas (event vazio -> 200)
  2. wpp-gateway-outbound _selftest synth: Polly (Camila) -> ffmpeg OGG/Opus -> S3
  3. wpp-gateway-inbound  _selftest transcribe: OGG/Opus -> Transcribe Streaming pt-BR -> texto
Encadeia 2->3 (o audio gerado no passo 2 e transcrito no passo 3), exercitando
Polly, ffmpeg (layer), S3, Transcribe Streaming e awscrt (layer) de ponta a ponta.

Uso: source .env && python3 scripts/test_voice_smoke.py
"""
import boto3
import json
import os
import sys
import time

REGION = os.environ.get('AWS_REGION', 'us-east-1')
lam = boto3.client('lambda', region_name=REGION)

FRASE = 'Ola, este e um teste de voz do assistente virtual.'
results = []


def invoke(name, payload):
    t0 = time.time()
    resp = lam.invoke(FunctionName=name, InvocationType='RequestResponse',
                      Payload=json.dumps(payload))
    dt = time.time() - t0
    body = json.loads(resp['Payload'].read() or 'null')
    ferr = resp.get('FunctionError')
    return body, ferr, dt


def check(nome, ok, latencia, nota=''):
    results.append((nome, 'PASS' if ok else 'FALHA', f'{latencia:.1f}s', nota))
    print(f'  [{"PASS" if ok else "FALHA"}] {nome} ({latencia:.1f}s) {nota}')


print('=== 1. Runtime/import health ===')
for fn in ['wpp-gateway-inbound', 'wpp-gateway-outbound']:
    body, ferr, dt = invoke(fn, {'Records': []})
    ok = ferr is None
    check(f'health {fn}', ok, dt, '' if ok else f'FunctionError={ferr}: {str(body)[:200]}')

print('\n=== 2. Synth (Polly Camila -> ffmpeg OGG/Opus -> S3) ===')
body, ferr, dt = invoke('wpp-gateway-outbound', {'_selftest': {'action': 'synth', 'text': FRASE}})
ogg_key = (body or {}).get('ogg_key')
bucket = (body or {}).get('bucket')
ok_synth = ferr is None and bool(ogg_key)
check('polly+ffmpeg synth', ok_synth, dt,
      f'ogg={ogg_key}' if ok_synth else f'FunctionError={ferr}: {str(body)[:200]}')

print('\n=== 3. Transcribe (OGG/Opus -> texto pt-BR) ===')
if ok_synth:
    body, ferr, dt = invoke('wpp-gateway-inbound',
                            {'_selftest': {'action': 'transcribe', 'bucket': bucket, 'key': ogg_key}})
    trans = (body or {}).get('transcription', '') or ''
    ok_trans = ferr is None and len(trans.strip()) > 0
    # heuristica: alguma palavra-chave da frase deve aparecer
    hit = any(w in trans.lower() for w in ['teste', 'voz', 'assistente', 'ola', 'ola,'])
    check('transcribe streaming', ok_trans and hit, dt,
          f'texto={trans!r}' if ok_trans else f'FunctionError={ferr}: {str(body)[:200]}')
else:
    check('transcribe streaming', False, 0.0, 'pulado (synth falhou)')

print('\n=== RESUMO ===')
allpass = all(r[1] == 'PASS' for r in results)
for nome, res, lat, nota in results:
    print(f'  {res:5} | {lat:>6} | {nome} {("- " + nota) if nota else ""}')
print('\n' + ('TODOS OS SMOKE TESTS PASSARAM' if allpass else 'HOUVE FALHAS - ver acima'))
sys.exit(0 if allpass else 1)
