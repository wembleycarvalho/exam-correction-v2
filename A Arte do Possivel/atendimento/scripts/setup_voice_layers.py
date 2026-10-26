"""
Cria as Lambda Layers da migracao de voz (x86_64, python3.12):
  1. ffmpeg-layer         -> /opt/bin/ffmpeg (+ffprobe)  [static build linux amd64]
  2. wpp-voice-deps-layer -> /opt/python: amazon-transcribe, awscrt (linux), requests

Publica as duas e salva os ARNs no .env (FFMPEG_LAYER_ARN, VOICE_DEPS_LAYER_ARN).

Uso: source .env && python3 scripts/setup_voice_layers.py
Requer: curl, tar (xz), pip3, acesso a internet.
"""
import boto3
import os
import sys
import subprocess
import tempfile
import shutil
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from env_helper import get_env, set_env

REGION = get_env('AWS_REGION', 'us-east-1')
LAYER_BUCKET = get_env('MEDIA_BUCKET', '')
lam = boto3.client('lambda', region_name=REGION)
s3c = boto3.client('s3', region_name=REGION)

FFMPEG_URL = 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz'
PY_VERSION = '3.12'


def zip_dir(src_dir, zip_path):
    base = zip_path[:-4] if zip_path.endswith('.zip') else zip_path
    shutil.make_archive(base, 'zip', src_dir)
    return base + '.zip'


def publish_layer(name, zip_path, desc):
    size = os.path.getsize(zip_path)
    print(f'  publicando {name} ({size//1024} KB)...')
    # Upload direto so vale pra zips pequenos (base64 infla ~33%, limite ~70MB de request).
    # Pra zips grandes (ffmpeg), sobe pro S3 e publica de la (ate 250MB unzipped).
    if size < 45 * 1024 * 1024:
        with open(zip_path, 'rb') as f:
            content = {'ZipFile': f.read()}
    else:
        key = f'layers/{name}.zip'
        print(f'    (grande) upload -> s3://{LAYER_BUCKET}/{key}')
        s3c.upload_file(zip_path, LAYER_BUCKET, key)
        content = {'S3Bucket': LAYER_BUCKET, 'S3Key': key}
    resp = lam.publish_layer_version(
        LayerName=name,
        Description=desc,
        Content=content,
        CompatibleRuntimes=['python3.12'],
        CompatibleArchitectures=['x86_64'],
    )
    arn = resp['LayerVersionArn']
    print(f'  {name}: {arn}')
    return arn


# ============================================================ 1. ffmpeg layer
def build_ffmpeg_layer():
    print('=== ffmpeg layer ===')
    tmp = tempfile.mkdtemp()
    try:
        tar_path = os.path.join(tmp, 'ffmpeg.tar.xz')
        print('  baixando static build...')
        urllib.request.urlretrieve(FFMPEG_URL, tar_path)
        subprocess.run(['tar', '-xf', tar_path, '-C', tmp], check=True)
        # encontra a pasta extraida
        extracted = next(os.path.join(tmp, d) for d in os.listdir(tmp)
                         if d.startswith('ffmpeg-') and os.path.isdir(os.path.join(tmp, d)))
        layer_root = os.path.join(tmp, 'layer')
        bin_dir = os.path.join(layer_root, 'bin')
        os.makedirs(bin_dir, exist_ok=True)
        for b in ['ffmpeg']:  # so ffmpeg (ffprobe nao e usado) -> layer menor
            src = os.path.join(extracted, b)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(bin_dir, b))
                os.chmod(os.path.join(bin_dir, b), 0o755)
        zip_path = zip_dir(layer_root, os.path.join(tmp, 'ffmpeg-layer.zip'))
        arn = publish_layer('ffmpeg-layer', zip_path, 'ffmpeg/ffprobe static amd64')
        set_env('FFMPEG_LAYER_ARN', arn)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================ 2. deps layer
def build_deps_layer():
    print('\n=== wpp-voice-deps layer ===')
    tmp = tempfile.mkdtemp()
    try:
        target = os.path.join(tmp, 'python')
        os.makedirs(target, exist_ok=True)
        # 1) pacotes puros (amazon-transcribe + requests). Isso tambem instala um awscrt
        #    do host (macOS) como dependencia -- que sera SOBRESCRITO no passo 2.
        print('  pip: amazon-transcribe + requests...')
        subprocess.run([
            'pip3', 'install', 'amazon-transcribe', 'requests',
            '--target', target, '--upgrade',
        ], check=True)
        # 2) awscrt para LINUX x86_64 por ULTIMO com --upgrade -> vence o wheel do host.
        print('  pip: awscrt (linux x86_64) [sobrescreve o do host]...')
        subprocess.run([
            'pip3', 'install', 'awscrt',
            '--platform', 'manylinux2014_x86_64',
            '--target', target,
            '--only-binary=:all:',
            '--python-version', PY_VERSION,
            '--upgrade',
        ], check=True)
        zip_path = zip_dir(tmp, os.path.join(tmp, 'deps-layer.zip'))
        # zip_dir zipa o tmp inteiro; garantir que so 'python/' esteja dentro
        # Recria zip apenas com a pasta python
        zip_only = os.path.join(tempfile.gettempdir(), 'wpp-voice-deps')
        if os.path.exists(zip_only + '.zip'):
            os.remove(zip_only + '.zip')
        # monta estrutura limpa
        clean = tempfile.mkdtemp()
        shutil.copytree(target, os.path.join(clean, 'python'))
        zip_path = zip_dir(clean, zip_only + '.zip')
        arn = publish_layer('wpp-voice-deps', zip_path,
                            'amazon-transcribe + awscrt(linux) + requests')
        set_env('VOICE_DEPS_LAYER_ARN', arn)
        shutil.rmtree(clean, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if which in ('all', 'ffmpeg'):
        build_ffmpeg_layer()
    if which in ('all', 'deps'):
        build_deps_layer()
    print('\n=== LAYERS PRONTAS ===')
