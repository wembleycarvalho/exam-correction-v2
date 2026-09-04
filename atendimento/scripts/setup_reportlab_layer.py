"""
Cria Lambda Layer com reportlab para geracao de PDF.
Uso: source .env && python3 scripts/setup_reportlab_layer.py
"""
import subprocess
import zipfile
import os
import shutil
import sys
import boto3
sys.path.insert(0, os.path.dirname(__file__))
from env_helper import get_env, set_env

REGION = get_env('AWS_REGION', 'us-east-1')
lmb = boto3.client('lambda', region_name=REGION)

LAYER_DIR = '/tmp/reportlab-layer'
ZIP_PATH = '/tmp/reportlab-layer.zip'

print('1. Installing reportlab...')
if os.path.exists(LAYER_DIR):
    shutil.rmtree(LAYER_DIR)
subprocess.run([
    'pip', 'install', 'reportlab', '-t', f'{LAYER_DIR}/python',
    '--upgrade', '--quiet', '--platform', 'manylinux2014_x86_64',
    '--only-binary=:all:', '--python-version', '3.12'
], check=True)

print('2. Creating zip...')
with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(LAYER_DIR):
        for f in files:
            full = os.path.join(root, f)
            zf.write(full, os.path.relpath(full, LAYER_DIR))
size_mb = os.path.getsize(ZIP_PATH) / (1024 * 1024)
print(f'   Size: {size_mb:.1f} MB')

print('3. Publishing layer...')
with open(ZIP_PATH, 'rb') as f:
    resp = lmb.publish_layer_version(
        LayerName='reportlab-layer',
        Content={'ZipFile': f.read()},
        CompatibleRuntimes=['python3.12'],
        Description='reportlab for PDF generation'
    )

layer_arn = resp['LayerVersionArn']
set_env('REPORTLAB_LAYER_ARN', layer_arn)
print(f'\nDone! Layer: {layer_arn}')
