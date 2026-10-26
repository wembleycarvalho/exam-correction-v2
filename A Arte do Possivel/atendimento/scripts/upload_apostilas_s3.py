"""
Upload de todos os PDFs e metadata JSONs para o bucket S3 da Knowledge Base.
Faz upload recursivo de output/apostilas/ preservando a estrutura de diretórios.

Estrutura no S3:
  publico/edital_vestibular_2026_2.pdf
  publico/sobre_instituicao.pdf
  privado/graduacao/eng-software/*.pdf
  privado/extensao/ext-*/*.pdf
  (+ .metadata.json para cada PDF)

Uso: source .env && python3 scripts/upload_apostilas_s3.py
"""
import boto3
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env

REGION = get_env('AWS_REGION', 'us-east-1')
BUCKET_NAME = require_env('KB_VESTIBULAR_BUCKET')
BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output', 'apostilas')

s3 = boto3.client('s3', region_name=REGION)


def get_content_type(filename):
    """Retorna o ContentType correto baseado na extensão do arquivo."""
    if filename.endswith('.pdf'):
        return 'application/pdf'
    elif filename.endswith('.json'):
        return 'application/json'
    return 'application/octet-stream'


def upload_file(local_path, s3_key):
    """Faz upload de um arquivo para o S3."""
    content_type = get_content_type(s3_key)
    with open(local_path, 'rb') as f:
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=f.read(),
            ContentType=content_type
        )


def main():
    print(f'=== Upload Apostilas para S3 ===')
    print(f'  Bucket: {BUCKET_NAME}')
    print(f'  Source: {BASE_DIR}')
    print()

    if not os.path.isdir(BASE_DIR):
        print(f'ERRO: Diretorio {BASE_DIR} nao encontrado.')
        print('Execute os scripts de geracao primeiro (gerar_apostilas.py, gerar_metadata.py, etc).')
        raise SystemExit(1)

    uploaded = 0
    errors = 0

    for root, dirs, files in os.walk(BASE_DIR):
        for filename in sorted(files):
            local_path = os.path.join(root, filename)
            # S3 key = caminho relativo a partir de output/apostilas/
            s3_key = os.path.relpath(local_path, BASE_DIR)

            try:
                upload_file(local_path, s3_key)
                uploaded += 1
                print(f'  [{uploaded}] {s3_key}')
            except Exception as e:
                errors += 1
                print(f'  ERRO: {s3_key} -> {e}')

    print()
    print(f'=== Resultado ===')
    print(f'  Arquivos enviados: {uploaded}')
    if errors:
        print(f'  Erros: {errors}')
    else:
        print(f'  Erros: 0')
    print(f'  Bucket: s3://{BUCKET_NAME}/')
    # ============================================================
    # Re-sincronizar a KB do Bedrock (start ingestion job)
    # ============================================================
    print()
    print('=== Re-sincronizar KB do Bedrock ===')

    kb_id = get_env('KB_VESTIBULAR_ID')
    if not kb_id:
        print('  AVISO: KB_VESTIBULAR_ID nao definido no .env. Pulando sync.')
        print('  Execute setup_kb_vestibular.py primeiro ou defina KB_VESTIBULAR_ID no .env.')
        return

    print(f'  KB ID: {kb_id}')

    try:
        bedrock_agent = boto3.client('bedrock-agent', region_name=REGION)

        # Listar data sources da KB e usar o primeiro
        ds_resp = bedrock_agent.list_data_sources(knowledgeBaseId=kb_id)
        data_sources = ds_resp.get('dataSourceSummaries', [])

        if not data_sources:
            print('  ERRO: Nenhum data source encontrado na KB.')
            print('  Verifique se a KB foi configurada corretamente.')
            return

        ds_id = data_sources[0]['dataSourceId']
        ds_name = data_sources[0].get('name', 'N/A')
        print(f'  Data Source: {ds_id} ({ds_name})')

        # Iniciar ingestion job (roda em background)
        bedrock_agent.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id
        )
        print('  Sync iniciado com sucesso (roda em background)')
        print('  A indexacao dos documentos pode levar alguns minutos.')

    except Exception as e:
        print(f'  ERRO ao sincronizar KB: {e}')
        print('  Voce pode sincronizar manualmente pelo console do Bedrock.')


if __name__ == '__main__':
    main()
