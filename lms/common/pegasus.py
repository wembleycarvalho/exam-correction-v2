"""Cliente do TwelveLabs Pegasus 1.2 no Amazon Bedrock (vídeo→texto: resumo/Q&A).

InvokeModel (síncrono). Body: {inputPrompt, mediaSource:{base64String|s3Location}, temperature,
maxOutputTokens} → {message, finishReason}. Vídeo inline (base64) até 25 MB — nossos clipes
são pequenos, então evitamos leitura cross-region do S3 pelo serviço.
"""
from __future__ import annotations

import json

from common import config


def build_body(prompt: str, *, video_b64: str = "", s3_uri: str = "", bucket_owner: str = "",
               max_tokens: int = 1024, temperature: float = 0.2) -> dict:
    if video_b64:
        media = {"base64String": video_b64}
    elif s3_uri:
        media = {"s3Location": {"uri": s3_uri, "bucketOwner": bucket_owner}}
    else:
        raise ValueError("informe video_b64 ou s3_uri")
    return {"inputPrompt": prompt[:8000], "mediaSource": media,
            "maxOutputTokens": int(max_tokens), "temperature": float(temperature)}


def parse_message(body: dict) -> tuple[str, str]:
    return body.get("message", ""), body.get("finishReason", "")


class Pegasus:
    def __init__(self, region: str | None = None, model_id: str | None = None, client=None):
        self.region = region or config.PEGASUS_REGION
        self.model_id = model_id or config.PEGASUS_MODEL_ID
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._client

    def analyze(self, prompt: str, *, video_b64: str = "", s3_uri: str = "",
                bucket_owner: str = "", max_tokens: int = 1024,
                temperature: float = 0.2) -> tuple[str, str]:
        body = build_body(prompt, video_b64=video_b64, s3_uri=s3_uri, bucket_owner=bucket_owner,
                          max_tokens=max_tokens, temperature=temperature)
        resp = self.client.invoke_model(
            modelId=self.model_id, contentType="application/json", accept="application/json",
            body=json.dumps(body))
        return parse_message(json.loads(resp["body"].read()))
