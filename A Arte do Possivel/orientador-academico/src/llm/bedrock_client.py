"""Thin wrapper around Amazon Bedrock (Converse API) for Nova/Claude models.

Uses the Converse API so the same code works with Amazon Nova and Anthropic Claude.
Model id is parameterized (never hardcoded in business logic) via env or constructor.
"""
from __future__ import annotations

import os


class BedrockLLM:
    def __init__(self, model_id: str | None = None, region: str | None = None):
        self.model_id = model_id or os.environ.get("ORIENTADOR_MODEL_ID", "amazon.nova-lite-v1:0")
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._client = None  # lazy: só cria o client boto3 quando realmente for chamar

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._client

    def complete(self, user: str, system: str | None = None,
                 max_tokens: int = 1024, temperature: float = 0.2) -> str:
        """Single-turn completion. Returns the assistant text."""
        kwargs = {
            "modelId": self.model_id,
            "messages": [{"role": "user", "content": [{"text": user}]}],
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
        }
        if system:
            kwargs["system"] = [{"text": system}]
        resp = self.client.converse(**kwargs)
        return resp["output"]["message"]["content"][0]["text"].strip()
