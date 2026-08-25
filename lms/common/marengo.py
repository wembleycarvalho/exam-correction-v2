"""Cliente do TwelveLabs Marengo Embed 3.0 no Amazon Bedrock.

Estrutura de input ANINHADA da v3 (twelvelabs.marengo-embed-3-0-v1:0):
- texto/imagem  -> InvokeModel (síncrono), resposta no corpo;
- vídeo/áudio   -> StartAsyncInvoke (assíncrono), embeddings gravados no S3.

Os *builders* de request e o parser de resposta são funções puras (testáveis sem AWS); as
chamadas boto3 ficam em métodos finos.
"""
from __future__ import annotations

import json

from . import config


# --------------------------- builders de input (puros) --------------------------- #
def text_input(text: str) -> dict:
    return {"inputType": "text", "text": {"inputText": text}}


def image_input_b64(b64: str) -> dict:
    return {"inputType": "image", "image": {"mediaSource": {"base64String": b64}}}


def image_input_s3(uri: str, bucket_owner: str) -> dict:
    return {"inputType": "image",
            "image": {"mediaSource": {"s3Location": {"uri": uri, "bucketOwner": bucket_owner}}}}


def _media_s3(kind: str, uri: str, bucket_owner: str, *, embedding_option, segmentation,
              embedding_scope) -> dict:
    # v3: embeddingOption/embeddingScope/segmentation vão DENTRO do objeto da modalidade
    # (não no topo do body — a API rejeita com "Extra inputs are not permitted").
    media = {"mediaSource": {"s3Location": {"uri": uri, "bucketOwner": bucket_owner}}}
    if embedding_option:
        media["embeddingOption"] = list(embedding_option)
    if embedding_scope:
        media["embeddingScope"] = list(embedding_scope)
    if segmentation:
        media["segmentation"] = segmentation
    return {"inputType": kind, kind: media}


def video_input_s3(uri: str, bucket_owner: str, *,
                   embedding_option=("visual", "audio", "transcription"),
                   embedding_scope=("clip",), segmentation=None) -> dict:
    return _media_s3("video", uri, bucket_owner, embedding_option=embedding_option,
                     segmentation=segmentation, embedding_scope=embedding_scope)


def audio_input_s3(uri: str, bucket_owner: str, *,
                   embedding_option=("audio", "transcription"),
                   embedding_scope=("clip",), segmentation=None) -> dict:
    return _media_s3("audio", uri, bucket_owner, embedding_option=embedding_option,
                     segmentation=segmentation, embedding_scope=embedding_scope)


def audio_input_b64(b64: str, *, embedding_option=("audio",), embedding_scope=("clip",)) -> dict:
    """Áudio inline (base64) — usado na busca por voz sem precisar subir o clipe ao S3.
    Atenção: o payload do request não pode passar de 25 MB (cota do Bedrock)."""
    media = {"mediaSource": {"base64String": b64}}
    if embedding_option:
        media["embeddingOption"] = list(embedding_option)
    if embedding_scope:
        media["embeddingScope"] = list(embedding_scope)
    return {"inputType": "audio", "audio": media}


def fixed_segmentation(duration_sec: int = 6) -> dict:
    return {"method": "fixed", "fixed": {"durationSec": int(duration_sec)}}


def dynamic_segmentation(min_duration_sec: int = 4) -> dict:
    return {"method": "dynamic", "dynamic": {"minDurationSec": int(min_duration_sec)}}


# --------------------------- parser de resposta (puro) --------------------------- #
def parse_embeddings(body: dict) -> list[dict]:
    """Normaliza a resposta em uma lista de dicts:
    {embedding: [...], modality: str|None, scope: str|None, start_sec: float|None, end_sec}.

    Aceita as variações: `{"data": {...}}`, `{"data": [ {...}, ... ]}` e listas de objetos
    `{"data": {"embedding": ...}}`.
    """
    if body is None:
        return []
    data = body.get("data", body)
    items = data if isinstance(data, list) else [data]
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        # cada item pode ser {"data": {...}} (async) ou {...} direto (sync)
        d = it.get("data", it)
        emb = d.get("embedding")
        if emb is None:
            continue
        opt = d.get("embeddingOption")
        modality = opt[0] if isinstance(opt, list) and opt else (opt if isinstance(opt, str) else None)
        scope = d.get("embeddingScope")
        scope = scope[0] if isinstance(scope, list) and scope else scope
        out.append({
            "embedding": [float(x) for x in emb],
            "modality": modality,
            "scope": scope,
            "start_sec": d.get("startSec"),
            "end_sec": d.get("endSec"),
        })
    return out


# --------------------------- cliente (boto3) --------------------------- #
class Marengo:
    def __init__(self, region: str | None = None, model_id: str | None = None, client=None):
        self.region = region or config.REGION
        self.model_id = model_id or config.MARENGO_MODEL_ID
        self._client = client  # injeta em testes

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._client

    # ---- síncrono (query de texto/imagem) ----
    def invoke(self, model_input: dict) -> list[dict]:
        resp = self.client.invoke_model(
            modelId=self.model_id, contentType="application/json", accept="application/json",
            body=json.dumps(model_input))
        return parse_embeddings(json.loads(resp["body"].read()))

    def embed_text(self, text: str) -> list[float]:
        embs = self.invoke(text_input(text))
        return embs[0]["embedding"] if embs else []

    def embed_image_b64(self, b64: str) -> list[float]:
        embs = self.invoke(image_input_b64(b64))
        return embs[0]["embedding"] if embs else []

    # ---- assíncrono (ingestão de vídeo / query por áudio) ----
    def start_async(self, model_input: dict, output_s3_uri: str) -> str:
        resp = self.client.start_async_invoke(
            modelId=self.model_id, modelInput=model_input,
            outputDataConfig={"s3OutputDataConfig": {"s3Uri": output_s3_uri}})
        return resp["invocationArn"]

    def get_async(self, invocation_arn: str) -> dict:
        return self.client.get_async_invoke(invocationArn=invocation_arn)
