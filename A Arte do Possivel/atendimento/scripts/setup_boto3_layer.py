"""
Cria Lambda Layer com boto3 atualizado.
Uso: source .env && python3 scripts/setup_boto3_layer.py
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

LAYER_DIR = '/tmp/boto3-layer'
ZIP_PATH = '/tmp/boto3-layer.zip'

print('1. Installing boto3...')
if os.path.exists(LAYER_DIR):
    shutil.rmtree(LAYER_DIR)
subprocess.run(['pip', 'install', 'boto3', 'botocore', '-t', f'{LAYER_DIR}/python', '--upgrade', '--quiet'], check=True)

print('2. Creating zip...')
with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(LAYER_DIR):
        for f in files:
            full = os.path.join(root, f)
            zf.write(full, os.path.relpath(full, LAYER_DIR))
print(f'   Size: {os.path.getsize(ZIP_PATH) / (1024*1024):.1f} MB')

print('3. Publishing layer...')
with open(ZIP_PATH, 'rb') as f:
    resp = lmb.publish_layer_version(
        LayerName='boto3-latest',
        Content={'ZipFile': f.read()},
        CompatibleRuntimes=['python3.12'],
        Description='Latest boto3 with invoke_harness support'
    )

layer_arn = resp['LayerVersionArn']
set_env('BOTO3_LAYER_ARN', layer_arn)
print(f'\nDone! Layer: {layer_arn}')
