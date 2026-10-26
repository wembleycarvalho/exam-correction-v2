"""Configuração do módulo LMS de vídeo (lida de variáveis de ambiente, injetadas via CDK).

Sem segredos aqui; apenas nomes de recursos e ids de modelo (parametrizados, nunca fixos no
código de negócio). Ver design.md do spec lms-video.
"""
import os

# Região: Marengo Embed 3.0 e S3 Vectors no mesmo lugar (base models em us-east-1).
REGION = os.environ.get("AWS_REGION", "us-east-1")

# --- Modelos Bedrock (TwelveLabs) ---
MARENGO_MODEL_ID = os.environ.get("LMS_MARENGO_MODEL_ID", "twelvelabs.marengo-embed-3-0-v1:0")
# Marengo Embed 3.0 = 512 dimensões (reduzido de 1024 na 2.7). Fixa a dimensão do índice.
EMBED_DIM = int(os.environ.get("LMS_EMBED_DIM", "512"))
# Pegasus 1.2 (vídeo→texto: resumo/Q&A) — fase 2. On-demand exige inference profile
# (cross-region); o perfil `us.` é invocável de us-east-1.
PEGASUS_MODEL_ID = os.environ.get("LMS_PEGASUS_MODEL_ID", "us.twelvelabs.pegasus-1-2-v1:0")
PEGASUS_REGION = os.environ.get("LMS_PEGASUS_REGION", "us-east-1")

# Modalidades de embedding geradas para cada clip de vídeo (any-to-any num índice só).
MODALITIES = ("visual", "audio", "transcription")

# --- S3 Vectors ---
VECTOR_BUCKET = os.environ.get("LMS_VECTOR_BUCKET", "")
VECTOR_INDEX = os.environ.get("LMS_VECTOR_INDEX", "lms-segments")
DISTANCE_METRIC = os.environ.get("LMS_DISTANCE_METRIC", "cosine")
# Metadados que NÃO serão usados como filtro (texto de referência). Não dá pra alterar
# depois de criar o índice — planejar com cuidado.
NON_FILTERABLE_KEYS = ("narration", "chapter_title", "name")

# --- S3 acervo/saída de embeddings ---
MEDIA_BUCKET = os.environ.get("LMS_MEDIA_BUCKET", "")
# Prefixo do acervo = mesmo path servido pelo CloudFront (/lms/media/*). Assim a chave S3
# casa com a URL sem reescrita: request /lms/media/<video> -> objeto lms/media/<video>.
MEDIA_PREFIX = os.environ.get("LMS_MEDIA_PREFIX", "lms/media/")
EMBED_OUTPUT_PREFIX = os.environ.get("LMS_EMBED_OUTPUT_PREFIX", "embeddings/")
ACCOUNT_ID = os.environ.get("LMS_ACCOUNT_ID", "")  # bucketOwner nas mediaSource S3

# --- DynamoDB ---
CATALOG_TABLE = os.environ.get("LMS_CATALOG_TABLE", "")
INGEST_TABLE = os.environ.get("LMS_INGEST_TABLE", "")

# --- Base de mídia servida pelo CloudFront (deep-link do player) ---
MEDIA_BASE_PATH = os.environ.get("LMS_MEDIA_BASE_PATH", "/lms/media")

# --- Busca ---
DEFAULT_TOP_K = int(os.environ.get("LMS_TOP_K", "12"))
