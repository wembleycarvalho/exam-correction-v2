"""Extração robusta de JSON da saída de um modelo (pode vir com cercas ```)."""
import json
import re


def extract_json(text: str):
    if not text or not text.strip():
        raise ValueError("Resposta do modelo vazia.")
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    match = re.search(r"(\{.*\}|\[.*\])", t, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    raise ValueError("JSON não encontrado na resposta do modelo.")
