"""Testes da lógica de busca e do roteador (com fakes de Marengo/Vectors/Store)."""
import json

from api import handler as api
from api import search as S


# --------------------------- fakes --------------------------- #
class FakeMarengo:
    model_id = "fake-marengo"

    def embed_text(self, text):
        return [0.1, 0.2, 0.3]

    def embed_image_b64(self, b64):
        return [0.4, 0.5, 0.6]


def _vec(disc, video, start, modality, dist, programs=("eng-software",), area="Computação"):
    return {"distance": dist, "metadata": {
        "disc_id": disc, "name": disc, "area": area, "programs": list(programs),
        "video": video, "modality": modality, "start_sec": start, "end_sec": start + 4,
        "chapter_index": 0, "chapter_title": "Cap", "narration": "n"}}


class FakeVectors:
    bucket = "vec-bucket"
    index = "vec-index"

    def __init__(self, vectors):
        self._vectors = vectors
        self.last_filter = "unset"
        self.last_topk = None

    def query(self, vector, top_k=None, flt=None, **kw):
        self.last_filter = flt
        self.last_topk = top_k
        return self._vectors


# --------------------------- filtros --------------------------- #
def test_build_index_filter():
    assert S.build_index_filter(None, None, None) is None
    f = S.build_index_filter({"area": "Física", "semester": 3}, "visual", None)
    assert f == {"area": "Física", "semester": 3, "modality": "visual"}
    # escopo por disciplina tem precedência
    f2 = S.build_index_filter({"disc_id": "x"}, None, {"disc_id": "disc_009"})
    assert f2 == {"disc_id": "disc_009"}


def test_dedupe_by_segment_keeps_best_and_sorts():
    hits = [S.SearchHit.from_vector(_vec("d", "v.mp4", 4.0, "visual", 0.5)),
            S.SearchHit.from_vector(_vec("d", "v.mp4", 4.0, "audio", 0.1)),   # melhor (score 0.9)
            S.SearchHit.from_vector(_vec("d", "v.mp4", 8.0, "visual", 0.3))]
    out = S.dedupe_by_segment(hits)
    assert len(out) == 2                      # 2 segmentos únicos
    assert out[0].start_sec == 4.0 and out[0].score == 0.9   # melhor primeiro


def test_apply_program_filter():
    hits = [S.SearchHit.from_vector(_vec("d", "v", 0, "visual", 0.1, programs=("eng-software",))),
            S.SearchHit.from_vector(_vec("d2", "v2", 0, "visual", 0.1, programs=("eng-mecanica",)))]
    out = S.apply_program_filter(hits, ["eng-mecanica"])
    assert len(out) == 1 and out[0].disc_id == "d2"


def test_group_catalog():
    disc = [{"area": "Computação", "programs": [{"code": "eng-software", "name": "Eng SW"}]},
            {"area": "Física", "programs": [{"code": "eng-mecanica", "name": "Eng Mec"}]}]
    g = S.group_catalog(disc)
    assert [c["code"] for c in g["courses"]] == ["eng-software", "eng-mecanica"] or \
           {c["code"] for c in g["courses"]} == {"eng-software", "eng-mecanica"}
    assert g["areas"] == ["Computação", "Física"]


# --------------------------- run_search --------------------------- #
def test_run_search_text_dedupes_and_deeplinks():
    vecs = [_vec("d", "computacao/x.mp4", 4.0, "visual", 0.5),
            _vec("d", "computacao/x.mp4", 4.0, "transcription", 0.05)]  # mesmo segmento
    fv = FakeVectors(vecs)
    out = S.run_search("text", marengo=FakeMarengo(), vectors=fv, text="pilhas",
                       top_k=5, media_base="/lms/media")
    assert fv.last_filter is None            # texto não filtra modalidade
    assert len(out) == 1                     # dedupe por segmento
    assert out[0]["deep_link"] == "/lms/media/computacao/x.mp4#t=4.0"
    assert out[0]["score"] == 0.95


def test_run_search_image_filters_visual():
    fv = FakeVectors([_vec("d", "v.mp4", 0.0, "visual", 0.2)])
    S.run_search("image", marengo=FakeMarengo(), vectors=fv, image_b64="B64",
                 filters={"area": "Computação"}, media_base="/lms/media")
    assert fv.last_filter == {"area": "Computação", "modality": "visual"}


def test_run_similar_excludes_self_and_filters_modality():
    src = _vec("d", "v.mp4", 4.0, "visual", 0.0)        # segmento de origem
    other = _vec("d2", "w.mp4", 0.0, "visual", 0.3)     # de outro curso/disc

    class FV(FakeVectors):
        def get(self, keys, return_data=True, return_metadata=True):
            return [{"data": {"float32": [0.1, 0.2, 0.3]}}]

    fv = FV([src, other])
    out = S.run_similar(disc_id="d", video="v.mp4", start_sec=4.0, vectors=fv,
                        modality="visual", media_base="/lms/media")
    assert fv.last_filter == {"modality": "visual"}
    # origem excluída; sobra o de outro curso (descoberta cruzada)
    assert not any(h["disc_id"] == "d" and h["deep_link"].endswith("v.mp4#t=4.0") for h in out)
    assert any(h["disc_id"] == "d2" for h in out)


def test_run_search_invalid_mode():
    try:
        S.run_search("bogus", marengo=FakeMarengo(), vectors=FakeVectors([]))
        assert False
    except ValueError:
        pass


# --------------------------- roteador --------------------------- #
class FakeStore:
    def list_catalog(self):
        return [{"area": "Computação", "programs": [{"code": "eng-software", "name": "Eng SW"}]}]


def test_handler_health_and_404():
    assert api.handler({"rawPath": "/lms/health",
                        "requestContext": {"http": {"method": "GET"}}})["statusCode"] == 200
    r = api.handler({"rawPath": "/lms/nope", "requestContext": {"http": {"method": "GET"}}})
    assert r["statusCode"] == 404


def test_handle_catalog():
    r = api.handle_catalog(FakeStore())
    assert r["statusCode"] == 200
    body = json.loads(r["body"])
    assert body["courses"][0]["code"] == "eng-software"


def test_handle_search_route():
    event = {"body": json.dumps({"mode": "text", "query": "pilhas", "top_k": 3})}
    fv = FakeVectors([_vec("d", "computacao/x.mp4", 4.0, "visual", 0.2)])
    r = api.handle_search(event, FakeMarengo(), fv)
    assert r["statusCode"] == 200
    body = json.loads(r["body"])
    assert body["mode"] == "text" and body["count"] == 1
    assert body["results"][0]["deep_link"].endswith("#t=4.0")
