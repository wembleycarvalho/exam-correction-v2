"""Ingestão de vídeos: Marengo (StartAsyncInvoke) → coleta embeddings no S3 → PutVectors no
S3 Vectors → catálogo/estado no DynamoDB. Idempotente por vídeo (chaves de vetor
determinísticas; catálogo/estado sobrescritos).

Ações (event["action"]):
- "start":   dispara o embedding assíncrono do vídeo (marca estado 'ingesting' + arn).
- "collect": checa o job; se concluído, coleta a saída, indexa e marca 'ready'.
- "ingest":  start + poll (limitado) + collect — conveniência para o script de deploy.

O `event` deve conter `discipline` (entrada do manifesto) OU `disc_id` (carrega do catálogo).
"""
from __future__ import annotations

import json
import time

from common import config
from common.manifest import Discipline, parse_discipline
from common.marengo import Marengo, parse_embeddings, video_input_s3
from common.segments import rows_from_embeddings
from common.store import Store
from common.vectors import VectorIndex


# --------------------------- helpers (puros) --------------------------- #
def split_s3_uri(uri: str) -> tuple[str, str]:
    assert uri.startswith("s3://"), uri
    rest = uri[5:]
    bucket, _, key = rest.partition("/")
    return bucket, key


def video_s3_uri(disc: Discipline) -> str:
    return f"s3://{config.MEDIA_BUCKET}/{config.MEDIA_PREFIX}{disc.video}"


def output_s3_uri(disc: Discipline) -> str:
    return f"s3://{config.MEDIA_BUCKET}/{config.EMBED_OUTPUT_PREFIX}{disc.discipline_id}/"


def catalog_entry(disc: Discipline) -> dict:
    """Documento do catálogo (DynamoDB) derivado do manifesto."""
    return {
        "disc_id": disc.discipline_id, "name": disc.name, "area": disc.area,
        "semester": disc.semester, "credits": disc.credits, "kb_slug": disc.kb_slug,
        "programs": disc.programs, "video": disc.video, "duration_sec": disc.duration_sec,
        "chapters": [
            {"index": c.index, "title": c.title, "start_sec": c.start_sec,
             "dur_sec": c.dur_sec, "voice": c.voice, "narration": c.narration}
            for c in disc.chapters
        ],
    }


# --------------------------- IO --------------------------- #
def _s3():
    import boto3
    return boto3.client("s3", region_name=config.REGION)


def read_output_embeddings(output_uri: str, s3=None) -> list[dict]:
    """Lê os JSONs de embedding gravados pelo job assíncrono sob o prefixo de saída e
    devolve a lista normalizada (via parse_embeddings)."""
    s3 = s3 or _s3()
    bucket, prefix = split_s3_uri(output_uri)
    items: list[dict] = []
    token = None
    while True:
        kw = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kw["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kw)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".json"):
                continue
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            try:
                items.extend(parse_embeddings(json.loads(body)))
            except Exception:  # noqa: BLE001
                continue
        if resp.get("IsTruncated"):
            token = resp.get("NextContinuationToken")
        else:
            break
    return items


# --------------------------- orquestração --------------------------- #
def _load_discipline(event: dict, store: Store) -> Discipline:
    if event.get("discipline"):
        return parse_discipline(event["discipline"])
    disc_id = event["disc_id"]
    doc = store.get_catalog(disc_id)
    if not doc:
        raise RuntimeError(f"disciplina {disc_id} não está no catálogo")
    return parse_discipline(doc)


def start(disc: Discipline, marengo: Marengo, store: Store) -> str:
    store.put_catalog(catalog_entry(disc))
    bucket_owner = config.ACCOUNT_ID or None
    body = video_input_s3(video_s3_uri(disc), bucket_owner or "",
                          embedding_option=config.MODALITIES, embedding_scope=("clip",))
    arn = marengo.start_async(body, output_s3_uri(disc))
    store.set_ingest(disc.video, "ingesting", disc_id=disc.discipline_id,
                     invocation_arn=arn, output_uri=output_s3_uri(disc))
    return arn


def collect(disc: Discipline, marengo: Marengo, store: Store, vectors: VectorIndex,
            s3=None) -> dict:
    state = store.get_ingest(disc.video) or {}
    arn = state.get("invocation_arn")
    if not arn:
        raise RuntimeError(f"sem invocation_arn para {disc.video} (rode 'start' antes)")
    info = marengo.get_async(arn)
    status = info.get("status")
    if status == "Completed":
        out = info.get("outputDataConfig", {}).get("s3OutputDataConfig", {}).get("s3Uri") \
            or state.get("output_uri") or output_s3_uri(disc)
        items = read_output_embeddings(out, s3=s3)
        rows = rows_from_embeddings(disc, items)
        n = vectors.put(rows) if rows else 0
        store.put_catalog(catalog_entry(disc))
        store.set_ingest(disc.video, "ready", disc_id=disc.discipline_id,
                         invocation_arn=arn, segments_count=n)
        return {"status": "ready", "segments": n}
    if status in ("Failed", "Expired"):
        store.set_ingest(disc.video, "failed", disc_id=disc.discipline_id,
                         invocation_arn=arn, error=info.get("failureMessage", status))
        return {"status": "failed", "error": info.get("failureMessage", status)}
    return {"status": status or "InProgress"}


def ingest(disc: Discipline, marengo: Marengo, store: Store, vectors: VectorIndex,
           *, poll_sec: int = 15, timeout_sec: int = 900, s3=None) -> dict:
    """start + poll + collect (para uso no script de deploy)."""
    start(disc, marengo, store)
    waited = 0
    while waited <= timeout_sec:
        res = collect(disc, marengo, store, vectors, s3=s3)
        if res["status"] in ("ready", "failed"):
            return res
        time.sleep(poll_sec)
        waited += poll_sec
    return {"status": "timeout"}


def handler(event, context=None):
    action = (event or {}).get("action", "ingest")
    store = Store()
    marengo = Marengo()
    vectors = VectorIndex()
    disc = _load_discipline(event, store)
    if action == "start":
        return {"invocation_arn": start(disc, marengo, store)}
    if action == "collect":
        return collect(disc, marengo, store, vectors)
    if action == "ingest":
        vectors.ensure_index()
        return ingest(disc, marengo, store, vectors)
    raise ValueError(f"ação desconhecida: {action}")
