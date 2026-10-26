"""
Upload de foto de cliente para o S3.

Uso:
  source .env && python3 scripts/upload_foto_cliente.py <cpf> <arquivo>
  source .env && python3 scripts/upload_foto_cliente.py 12345678900 ~/foto.jpg
  source .env && python3 scripts/upload_foto_cliente.py --bulk <pasta>   # upload em massa

Formatos aceitos: .jpg, .jpeg, .png, .webp
Para upload em massa, nomeie os arquivos como <cpf>.jpg, <cpf>.png, etc.

Exemplos:
  # Upload individual
  python3 scripts/upload_foto_cliente.py 12345678900 /path/to/foto.jpg

  # Upload em massa (todos os arquivos na pasta)
  python3 scripts/upload_foto_cliente.py --bulk /path/to/fotos/
  # Espera arquivos nomeados como: 12345678900.jpg, 98765432100.png, etc.
"""
import boto3
import os
import sys
import mimetypes
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import require_env, get_env

REGION = get_env('AWS_REGION', 'us-east-1')
ACCOUNT_ID = require_env('AWS_ACCOUNT_ID')
BUCKET_NAME = get_env('FOTOS_BUCKET', f'fotos-clientes-{ACCOUNT_ID}')

s3 = boto3.client('s3', region_name=REGION)

VALID_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def upload_foto(cpf, filepath):
    """Upload de uma foto para S3."""
    if not os.path.exists(filepath):
        print(f'  ERRO: Arquivo nao encontrado: {filepath}')
        return False

    ext = os.path.splitext(filepath)[1].lower()
    if ext not in VALID_EXTENSIONS:
        print(f'  ERRO: Formato nao suportado: {ext} (use .jpg, .png, .webp)')
        return False

    # Normalizar extensao
    if ext == '.jpeg':
        ext = '.jpg'

    key = f'fotos/{cpf}{ext}'
    content_type = mimetypes.guess_type(filepath)[0] or 'image/jpeg'

    file_size = os.path.getsize(filepath)
    if file_size > 5 * 1024 * 1024:  # 5MB limit
        print(f'  AVISO: Arquivo grande ({file_size / 1024 / 1024:.1f}MB). Recomendado < 5MB.')

    s3.upload_file(
        filepath,
        BUCKET_NAME,
        key,
        ExtraArgs={
            'ContentType': content_type,
            'Metadata': {'cpf': cpf}
        }
    )
    print(f'  OK: {cpf} -> s3://{BUCKET_NAME}/{key} ({file_size / 1024:.0f}KB)')
    return True


def upload_bulk(folder):
    """Upload em massa de fotos na pasta."""
    if not os.path.isdir(folder):
        print(f'ERRO: Pasta nao encontrada: {folder}')
        sys.exit(1)

    files = [f for f in os.listdir(folder)
             if os.path.splitext(f)[1].lower() in VALID_EXTENSIONS]

    if not files:
        print(f'Nenhum arquivo de imagem encontrado em {folder}')
        sys.exit(1)

    print(f'Encontrados {len(files)} arquivos de imagem')
    print()

    success = 0
    errors = 0

    for filename in sorted(files):
        # CPF e o nome do arquivo sem extensao
        cpf = os.path.splitext(filename)[0]

        # Validar que parece um CPF (11 digitos)
        if not cpf.replace('.', '').replace('-', '').isdigit():
            print(f'  SKIP: {filename} (nome nao parece um CPF)')
            continue

        cpf_clean = cpf.replace('.', '').replace('-', '')
        filepath = os.path.join(folder, filename)

        try:
            if upload_foto(cpf_clean, filepath):
                success += 1
            else:
                errors += 1
        except Exception as e:
            print(f'  ERRO: {filename}: {e}')
            errors += 1

    print(f'\n=== Resultado ===')
    print(f'  Sucesso: {success}')
    print(f'  Erros: {errors}')


def list_fotos():
    """Lista fotos existentes no bucket."""
    print(f'=== Fotos no bucket {BUCKET_NAME} ===\n')
    paginator = s3.get_paginator('list_objects_v2')
    count = 0
    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix='fotos/'):
        for obj in page.get('Contents', []):
            key = obj['Key']
            size = obj['Size']
            modified = obj['LastModified'].strftime('%Y-%m-%d %H:%M')
            print(f'  {key} ({size / 1024:.0f}KB) - {modified}')
            count += 1
    if count == 0:
        print('  Nenhuma foto encontrada.')
    else:
        print(f'\n  Total: {count} fotos')


def delete_foto(cpf):
    """Remove foto de um cliente."""
    deleted = False
    for ext in ['jpg', 'png', 'webp']:
        key = f'fotos/{cpf}.{ext}'
        try:
            s3.head_object(Bucket=BUCKET_NAME, Key=key)
            s3.delete_object(Bucket=BUCKET_NAME, Key=key)
            print(f'  Deletado: s3://{BUCKET_NAME}/{key}')
            deleted = True
        except:
            pass
    if not deleted:
        print(f'  Nenhuma foto encontrada para CPF {cpf}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == '--bulk':
        folder = sys.argv[2] if len(sys.argv) > 2 else '.'
        upload_bulk(folder)
    elif cmd == '--list':
        list_fotos()
    elif cmd == '--delete':
        if len(sys.argv) < 3:
            print('Uso: upload_foto_cliente.py --delete <cpf>')
            sys.exit(1)
        delete_foto(sys.argv[2])
    else:
        # Upload individual: <cpf> <arquivo>
        cpf = sys.argv[1]
        if len(sys.argv) < 3:
            print('Uso: upload_foto_cliente.py <cpf> <arquivo>')
            print('     upload_foto_cliente.py --bulk <pasta>')
            print('     upload_foto_cliente.py --list')
            print('     upload_foto_cliente.py --delete <cpf>')
            sys.exit(1)
        filepath = sys.argv[2]
        print(f'=== Upload foto: CPF {cpf} ===')
        upload_foto(cpf, filepath)
