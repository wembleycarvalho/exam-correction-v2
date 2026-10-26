"""Testes das partes puras/IO-stubbed da ingestão."""
import json

from common import config
from common.manifest import parse_discipline
from common.segments import rows_from_embeddings
from ingest import handler as ing

DISC = {
    "discipline_id": "disc_005", "name": "Fundamentos de Computação", "area": "Computação",
    "semester": 1, "credits": 4, "kb_slug": "fundamentos_de_computacao",
    "programs": [{"id": "prog_es", "code": "eng-software", "name": "Engenharia de Software"}],
    "video": "computacao/disc_005_fundamentos_de_computacao.mp4", "duration_sec": 30.0,
    "chapters": [
        {"index": 0, "title": "Introdução", "start_sec": 0.0, "dur_sec": 6.0, "voice": "Camila",
         "narration": "Fundamentos. Primeiro tema: Introdução."},
        {"index": 1, "title": "Hardware básico", "start_sec": 6.0, "dur_sec": 6.0,
         "voice": "Thiago", "narration": "Tema: Hardware básico."},
    ],
}


def _disc():
    return parse_discipline(DISC)


def test_rows_from_embeddings_modalities_and_asset_skip():
    disc = _disc()
    items = [
        {"embedding": [0.1] * 3, "modality": "visual", "scope": "clip", "start_sec": 6.0, "end_sec": 10.0},
        {"embedding": [0.2] * 3, "modality": "audio", "scope": "clip", "start_sec": 6.0, "end_sec": 10.0},
        {"embedding": [0.3] * 3, "modality": "transcription", "scope": "clip", "start_sec": 6.0, "end_sec": 10.0},
        {"embedding": [0.9] * 3, "modality": "visual", "scope": "asset", "start_sec": 0.0, "end_sec": 30.0},
        {"embedding": None, "modality": "visual", "scope": "clip", "start_sec": 0.0, "end_sec": 6.0},
    ]
    rows = rows_from_embeddings(disc, items)
    assert len(rows) == 3  # asset e embedding vazio ignorados
    mods = {r["metadata"]["modality"] for r in rows}
    assert mods == {"visual", "audio", "transcription"}
    # centro do clip 6-10 = 8.0 -> capítulo 1 "Hardware básico"
    assert all(r["metadata"]["chapter_index"] == 1 for r in rows)
    assert all(r["metadata"]["chapter_title"] == "Hardware básico" for r in rows)
    keys = {r["key"] for r in rows}
    assert len(keys) == 3  # chave inclui a modalidade -> únicas


def test_default_modality_visual():
    disc = _disc()
    rows = rows_from_embeddings(disc, [{"embedding": [0.1], "start_sec": 0.0, "end_sec": 5.0}])
    assert rows[0]["metadata"]["modality"] == "visual"


def test_split_s3_uri():
    assert ing.split_s3_uri("s3://bucket/a/b/c.mp4") == ("bucket", "a/b/c.mp4")


def test_uris_and_catalog(monkeypatch):
    monkeypatch.setattr(config, "MEDIA_BUCKET", "media-b")
    monkeypatch.setattr(config, "MEDIA_PREFIX", "videos/")
    monkeypatch.setattr(config, "EMBED_OUTPUT_PREFIX", "embeddings/")
    disc = _disc()
    assert ing.video_s3_uri(disc) == "s3://media-b/videos/computacao/disc_005_fundamentos_de_computacao.mp4"
    assert ing.output_s3_uri(disc) == "s3://media-b/embeddings/disc_005/"
    cat = ing.catalog_entry(disc)
    assert cat["disc_id"] == "disc_005" and len(cat["chapters"]) == 2
    assert cat["programs"][0]["code"] == "eng-software"


class _FakeS3:
    """S3 mínimo para testar read_output_embeddings."""
    def __init__(self, objects: dict):
        self._objects = objects  # {key: bytes}

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
        keys = [k for k in self._objects if k.startswith(Prefix)]
        return {"Contents": [{"Key": k} for k in keys], "IsTruncated": False}

    def get_object(self, Bucket, Key):
        import io
        return {"Body": io.BytesIO(self._objects[Key])}


def test_read_output_embeddings():
    payload = {"data": [
        {"data": {"embedding": [0.1, 0.2], "embeddingOption": ["visual"], "embeddingScope": ["clip"],
                  "startSec": 0, "endSec": 4}},
        {"data": {"embedding": [0.3, 0.4], "embeddingOption": ["audio"], "embeddingScope": ["clip"],
                  "startSec": 0, "endSec": 4}},
    ]}
    fake = _FakeS3({
        "embeddings/disc_005/output.json": json.dumps(payload).encode(),
        "embeddings/disc_005/other.txt": b"ignore",
    })
    items = ing.read_output_embeddings("s3://media-b/embeddings/disc_005/", s3=fake)
    assert [i["modality"] for i in items] == ["visual", "audio"]
