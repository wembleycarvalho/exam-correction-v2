"""Router HTTP do módulo LMS (Lambda atrás do HTTP API + JWT Cognito, sob /lms/*).

Rotas:
- GET  /lms/health
- GET  /lms/catalog                 -> catálogo agrupado (cursos/áreas/disciplinas)
- POST /lms/search                  -> busca (mode: text|image|audio) + filtros/escopo
"""
from __future__ import annotations

import base64
import json
import time
import uuid

from api import search as search_mod
from common import config
from common.marengo import Marengo, audio_input_b64, audio_input_s3, parse_embeddings
from common.pegasus import Pegasus
from common.store import Store
from common.vectors import VectorIndex

BASE = "/lms"


# --------------------------- helpers HTTP --------------------------- #
def _resp(status: int, obj) -> dict:
    return {"statusCode": status,
            "headers": {"content-type": "application/json; charset=utf-8"},
            "body": json.dumps(obj, ensure_ascii=False)}


def _body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        return json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001
        return {}


def _route(event: dict) -> tuple[str, str]:
    rc = event.get("requestContext", {})
    method = rc.get("http", {}).get("method") or event.get("httpMethod", "GET")
    path = event.get("rawPath") or event.get("path") or "/"
    return method.upper(), path


# --------------------------- busca por áudio (async, best-effort) --------------------------- #
def embed_audio_query(audio_ref: dict, *, marengo: Marengo = None, s3=None,
                      poll_sec: int = 5, timeout_sec: int = 45) -> list[float]:
    """Embute um clipe de áudio (StartAsyncInvoke) e devolve o vetor 'audio'. Best-effort:
    limitado ao timeout do request. `audio_ref` = {s3_uri, bucket_owner} (recomendado)."""
    from ingest.handler import read_output_embeddings
    marengo = marengo or Marengo()
    audio_ref = audio_ref or {}
    if audio_ref.get("base64"):
        body = audio_input_b64(audio_ref["base64"], embedding_option=("audio",),
                               embedding_scope=("clip",))
    elif audio_ref.get("s3_uri"):
        body = audio_input_s3(audio_ref["s3_uri"],
                              audio_ref.get("bucket_owner") or config.ACCOUNT_ID or "",
                              embedding_option=("audio",), embedding_scope=("clip",))
    else:
        raise ValueError("busca por áudio requer base64 ou s3_uri em audio_ref")
    out = f"s3://{config.MEDIA_BUCKET}/{config.EMBED_OUTPUT_PREFIX}queries/{uuid.uuid4().hex}/"
    arn = marengo.start_async(body, out)
    waited = 0
    while waited <= timeout_sec:
        info = marengo.get_async(arn)
        if info.get("status") == "Completed":
            items = read_output_embeddings(
                info.get("outputDataConfig", {}).get("s3OutputDataConfig", {}).get("s3Uri", out),
                s3=s3)
            for it in items:
                if (it.get("modality") or "audio") == "audio" and it.get("embedding"):
                    return it["embedding"]
            return items[0]["embedding"] if items else []
        if info.get("status") in ("Failed", "Expired"):
            return []
        time.sleep(poll_sec)
        waited += poll_sec
    return []


# --------------------------- rotas --------------------------- #
def handle_catalog(store: Store) -> dict:
    return _resp(200, search_mod.group_catalog(store.list_catalog()))


def handle_search(event: dict, marengo: Marengo, vectors: VectorIndex) -> dict:
    b = _body(event)
    mode = b.get("mode", "text")
    dbg = {} if b.get("debug") else None
    try:
        results = search_mod.run_search(
            mode, marengo=marengo, vectors=vectors,
            video_embed_fn=lambda ref: embed_audio_query(ref, marengo=marengo),
            text=b.get("query", ""), image_b64=b.get("image_b64", ""),
            audio_ref=b.get("audio_ref"), filters=b.get("filters"), scope=b.get("scope"),
            top_k=b.get("top_k"), debug=dbg)
    except ValueError as e:
        return _resp(400, {"code": "invalid_request", "message": str(e)})
    out = {"mode": mode, "count": len(results), "results": results}
    if dbg is not None:
        out["debug"] = dbg
    return _resp(200, out)


def handle_similar(event: dict, vectors: VectorIndex) -> dict:
    b = _body(event)
    at_sec = b.get("at_sec")
    if not b.get("disc_id") or not b.get("video") or (at_sec is None and b.get("start_sec") is None):
        return _resp(400, {"code": "invalid_request",
                           "message": "disc_id, video e (at_sec ou start_sec) são obrigatórios"})
    dbg = {} if b.get("debug") else None
    results = search_mod.run_similar(
        disc_id=b["disc_id"], video=b["video"],
        start_sec=None if b.get("start_sec") is None else float(b["start_sec"]),
        at_sec=None if at_sec is None else float(at_sec),
        modality=b.get("modality", "visual"), vectors=vectors, top_k=b.get("top_k"), debug=dbg)
    out = {"count": len(results), "results": results}
    if dbg is not None:
        out["debug"] = dbg
    return _resp(200, out)


_PROMPT_SUMMARY = ("Você é um assistente educacional. Assista à videoaula e responda em "
                   "português do Brasil: um resumo objetivo em até 4 frases, seguido de 3 a 6 "
                   "tópicos principais em bullets começando com '- '. Não invente conteúdo.")


def _read_video_b64(video: str, s3=None) -> str:
    import base64
    import boto3
    s3 = s3 or boto3.client("s3", region_name=config.REGION)
    key = f"{config.MEDIA_PREFIX}{video}"
    data = s3.get_object(Bucket=config.MEDIA_BUCKET, Key=key)["Body"].read()
    return base64.b64encode(data).decode("ascii")


def handle_pegasus(event: dict, store: Store, pegasus: Pegasus, *, ask: bool) -> dict:
    b = _body(event)
    disc_id = b.get("disc_id")
    doc = store.get_catalog(disc_id) if disc_id else None
    if not doc:
        return _resp(404, {"code": "not_found", "message": "disciplina não encontrada no catálogo"})
    if ask:
        q = (b.get("question") or "").strip()
        if not q:
            return _resp(400, {"code": "invalid_request", "message": "question é obrigatório"})
        prompt = f"Responda em português do Brasil, com base apenas no conteúdo do vídeo: {q}"
    else:
        prompt = _PROMPT_SUMMARY
    trace = []
    try:
        t = time.perf_counter()
        b64 = _read_video_b64(doc["video"])
        trace.append({"passo": 1, "acao": "baixar o vídeo do S3 e codificar em base64",
                      "ms": round((time.perf_counter() - t) * 1000, 1),
                      "detalhe": {"video": doc["video"], "base64_chars": len(b64)}})
        t = time.perf_counter()
        message, finish = pegasus.analyze(prompt, video_b64=b64, max_tokens=1024)
        trace.append({"passo": 2, "acao": "invocar Pegasus (InvokeModel) com vídeo + prompt",
                      "ms": round((time.perf_counter() - t) * 1000, 1),
                      "detalhe": {"model_id": pegasus.model_id, "region": pegasus.region,
                                  "inputPrompt": prompt, "maxOutputTokens": 1024,
                                  "finishReason": finish, "message_chars": len(message)}})
    except Exception as e:  # noqa: BLE001
        return _resp(502, {"code": "pegasus_error", "message": str(e)})
    out = {"disc_id": disc_id, "name": doc.get("name", ""),
           "answer" if ask else "summary": message, "finish_reason": finish}
    if b.get("debug"):
        out["debug"] = {
            "fluxo": ("Envia o VÍDEO inteiro (base64) + um prompt ao Pegasus (InvokeModel). "
                      "O modelo assiste ao vídeo e devolve texto."),
            "trace": trace,
        }
    return _resp(200, out)


def handle_eval(event: dict, marengo: Marengo, vectors: VectorIndex, store: Store) -> dict:
    """Auto-avaliação (amostra): usa capítulos como consulta e mede acerto de timestamp.
    Limitada por `limit` disciplinas para caber no timeout do request."""
    from eval.evaluate import evaluate
    b = _body(event)
    k = int(b.get("k", 5))
    limit = int(b.get("limit", 5))
    disciplines = store.list_catalog()[:limit]

    def search_fn(query, _disc_id):
        return search_mod.run_search("text", marengo=marengo, vectors=vectors, text=query, top_k=k)

    report = evaluate(disciplines, search_fn, k=k, verbose=bool(b.get("verbose")))
    return _resp(200, report)


def handler(event, context=None):
    method, path = _route(event)
    if path == f"{BASE}/health":
        return _resp(200, {"status": "ok"})
    store = Store()
    if method == "GET" and path == f"{BASE}/catalog":
        return handle_catalog(store)
    if method == "POST" and path == f"{BASE}/search":
        return handle_search(event, Marengo(), VectorIndex())
    if method == "POST" and path == f"{BASE}/similar":
        return handle_similar(event, VectorIndex())
    if method == "POST" and path == f"{BASE}/summary":
        return handle_pegasus(event, store, Pegasus(), ask=False)
    if method == "POST" and path == f"{BASE}/ask":
        return handle_pegasus(event, store, Pegasus(), ask=True)
    if method == "POST" and path == f"{BASE}/eval":
        return handle_eval(event, Marengo(), VectorIndex(), store)
    return _resp(404, {"code": "not_found", "message": f"{method} {path}"})
