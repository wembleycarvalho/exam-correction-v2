"""Testes das partes puras do núcleo LMS (manifesto, segmentos, builders/parser Marengo)."""
from common import marengo
from common.manifest import parse_discipline
from common.segments import (
    SearchHit, chapter_for_time, segment_center, segment_key, segment_metadata, vector_row,
)

SAMPLE = {
    "discipline_id": "disc_029", "name": "Física II (Termodinâmica)", "area": "Física",
    "semester": 3, "credits": 4, "kb_slug": None,
    "programs": [{"id": "prog_mec", "code": "eng-mecanica", "name": "Engenharia Mecânica"}],
    "video": "fisica/disc_029_fisica_ii_termodinamica.mp4", "duration_sec": 20.0,
    "chapters": [
        {"index": 0, "title": "Leis da termodinâmica", "start_sec": 0.0, "dur_sec": 5.0,
         "voice": "Camila", "narration": "Física. Primeiro tema: Leis da termodinâmica."},
        {"index": 1, "title": "Equilíbrio térmico", "start_sec": 5.0, "dur_sec": 5.0,
         "voice": "Thiago", "narration": "Tema: Equilíbrio térmico."},
        {"index": 2, "title": "Motores térmicos", "start_sec": 10.0, "dur_sec": 5.0,
         "voice": "Vitoria", "narration": "Tema: Motores térmicos."},
    ],
}


def _disc():
    return parse_discipline(SAMPLE)


# --------------------------- manifesto --------------------------- #
def test_parse_discipline_and_programs():
    d = _disc()
    assert d.discipline_id == "disc_029"
    assert d.program_codes == ["eng-mecanica"]
    assert d.program_ids == ["prog_mec"]
    assert len(d.chapters) == 3
    assert d.chapters[0].end_sec == 5.0


# --------------------------- casamento segmento↔capítulo --------------------------- #
def test_chapter_for_time_inside_and_boundary():
    ch = _disc().chapters
    assert chapter_for_time(ch, 0.0).index == 0        # início
    assert chapter_for_time(ch, 4.99).index == 0       # dentro do 0
    assert chapter_for_time(ch, 5.0).index == 1        # borda -> próximo
    assert chapter_for_time(ch, 12.3).index == 2       # dentro do 2


def test_chapter_for_time_out_of_range():
    ch = _disc().chapters
    assert chapter_for_time(ch, -1.0).index == 0       # antes de tudo -> primeiro
    assert chapter_for_time(ch, 999.0).index == 2      # depois -> último início <= t
    assert chapter_for_time([], 3.0) is None


def test_segment_center():
    assert segment_center(0.0, 4.2) == 2.1


# --------------------------- chave/metadados/linha --------------------------- #
def test_segment_key_stable():
    assert segment_key("disc_029", "a/b.mp4", 4.0, "visual") == "disc_029#a/b.mp4#4.0#visual"


def test_segment_metadata_and_vector_row():
    d = _disc()
    center = segment_center(4.0, 8.0)  # 6.0 -> capítulo 1
    ch = chapter_for_time(d.chapters, center)
    row = vector_row(d, ch, embedding=[0.1, 0.2, 0.3], start_sec=4.0, end_sec=8.0,
                     modality="visual")
    assert row["key"] == "disc_029#fisica/disc_029_fisica_ii_termodinamica.mp4#4.0#visual"
    assert row["data"]["float32"] == [0.1, 0.2, 0.3]
    m = row["metadata"]
    assert m["disc_id"] == "disc_029"
    assert m["programs"] == ["eng-mecanica"]
    assert m["modality"] == "visual"
    assert m["chapter_index"] == 1
    assert m["chapter_title"] == "Equilíbrio térmico"
    assert m["start_sec"] == 4.0 and m["end_sec"] == 8.0


def test_search_hit_deeplink():
    v = {"distance": 0.2, "metadata": {
        "disc_id": "disc_029", "name": "Física II", "area": "Física",
        "programs": ["eng-mecanica"], "video": "fisica/x.mp4", "modality": "visual",
        "start_sec": 10.0, "end_sec": 14.0, "chapter_index": 2,
        "chapter_title": "Motores térmicos", "narration": "Tema: Motores térmicos."}}
    hit = SearchHit.from_vector(v)
    assert hit.score == 0.8          # 1 - distância
    d = hit.to_dict("/lms/media")
    assert d["deep_link"] == "/lms/media/fisica/x.mp4#t=10.0"
    assert d["media_url"] == "/lms/media/fisica/x.mp4"


# --------------------------- builders/parser Marengo --------------------------- #
def test_text_and_image_inputs():
    assert marengo.text_input("oi") == {"inputType": "text", "text": {"inputText": "oi"}}
    img = marengo.image_input_b64("BASE64")
    assert img["inputType"] == "image"
    assert img["image"]["mediaSource"]["base64String"] == "BASE64"


def test_video_input_s3_structure():
    seg = marengo.dynamic_segmentation(4)
    body = marengo.video_input_s3("s3://b/k.mp4", "123456789012",
                                  embedding_option=("visual", "audio", "transcription"),
                                  embedding_scope=("clip",), segmentation=seg)
    assert body["inputType"] == "video"
    assert body["video"]["mediaSource"]["s3Location"]["uri"] == "s3://b/k.mp4"
    assert body["video"]["mediaSource"]["s3Location"]["bucketOwner"] == "123456789012"
    # v3: parâmetros ficam DENTRO do objeto da modalidade
    assert body["video"]["embeddingOption"] == ["visual", "audio", "transcription"]
    assert body["video"]["embeddingScope"] == ["clip"]
    assert body["video"]["segmentation"]["method"] == "dynamic"


def test_audio_input_b64():
    b = marengo.audio_input_b64("AAAA")
    assert b["inputType"] == "audio"
    assert b["audio"]["mediaSource"]["base64String"] == "AAAA"
    assert b["audio"]["embeddingOption"] == ["audio"]
    assert b["audio"]["embeddingScope"] == ["clip"]


def test_pegasus_build_body_and_parse():
    from common import pegasus
    b = pegasus.build_body("resuma", video_b64="AAA", max_tokens=500, temperature=0.1)
    assert b["inputPrompt"] == "resuma"
    assert b["mediaSource"]["base64String"] == "AAA"
    assert b["maxOutputTokens"] == 500 and b["temperature"] == 0.1
    b2 = pegasus.build_body("q", s3_uri="s3://x/y.mp4", bucket_owner="123456789012")
    assert b2["mediaSource"]["s3Location"] == {"uri": "s3://x/y.mp4", "bucketOwner": "123456789012"}
    try:
        pegasus.build_body("sem mídia")
        assert False
    except ValueError:
        pass
    assert pegasus.parse_message({"message": "oi", "finishReason": "stop"}) == ("oi", "stop")


def test_parse_embeddings_variants():
    # dict único
    b1 = {"data": {"embedding": [0.1, 0.2], "embeddingOption": ["visual"],
                   "embeddingScope": ["clip"], "startSec": 0, "endSec": 4.2}}
    out1 = marengo.parse_embeddings(b1)
    assert len(out1) == 1 and out1[0]["modality"] == "visual" and out1[0]["end_sec"] == 4.2
    # lista de objetos com data aninhado (async)
    b2 = {"data": [{"data": {"embedding": [1.0], "embeddingOption": ["audio"]}},
                   {"data": {"embedding": [2.0], "embeddingOption": ["transcription"]}}]}
    out2 = marengo.parse_embeddings(b2)
    assert [o["modality"] for o in out2] == ["audio", "transcription"]
    # sem data (corpo direto)
    b3 = {"embedding": [9.0]}
    out3 = marengo.parse_embeddings(b3)
    assert out3[0]["embedding"] == [9.0]
