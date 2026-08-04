"""Correção de Provas Online (compartilhada API/worker).

Contém os helpers de Knowledge Base (RAG) e a correção de uma tentativa:
  - Múltipla escolha (mc): determinística (compara marcada vs correta).
  - Discursiva: usa a capacidade 'exam' (LLM) para nota + justificativa por questão.
Para questões erradas/fracas, sugere trechos das APOSTILAS do KB (com página) para estudo.

A API usa os helpers de KB na geração/download; o worker usa `grade()` no consumo da fila.
"""
import re

from common.model_config import get_model_config
from common.runtime_client import invoke_agent

_LETTERS = ("A", "B", "C", "D", "E", "F")
# Resposta discursiva "boa" (acerto p/ resumo) a partir de 60% da nota.
_DISC_PASS = 0.6


# --- Knowledge Base -------------------------------------------------------------
def kb_title(uri: str) -> str:
    """Nome legível a partir da URI S3 (sem caminho, extensão nem sufixo _email/_material)."""
    name = (uri or "").rsplit("/", 1)[-1]
    name = re.sub(r"\.[a-z0-9]+$", "", name, flags=re.I)
    name = re.sub(r"_(email|material)$", "", name, flags=re.I)
    return name.replace("_", " ").replace("-", " ").strip() or (uri or "")


def is_apostila(uri: str) -> bool:
    """Só apostilas: exclui os PDFs de e-mail (sufixo _email.pdf), que não são material de apoio."""
    return not (uri or "").lower().endswith("_email.pdf")


def is_material(uri: str) -> bool:
    """Apostila de conteúdo (sufixo _material.pdf) — não é a ementa/plano (base) nem e-mail."""
    return (uri or "").lower().endswith("_material.pdf")


STUDY_FETCH_N = 12  # nº de passagens recuperadas antes de filtrar/deduplicar


def study_sources(kb_client, kb_id: str, query: str, n: int = 2) -> list:
    """Sugestão de estudo: prioriza as APOSTILAS de conteúdo (_material.pdf), dedupe por
    título, com a página onde o trecho aparece. Cai para outros apostilas se não houver
    material específico. Evita sugerir a ementa/plano (base) e e-mails."""
    passages = kb_retrieve(kb_client, kb_id, query, n=STUDY_FETCH_N)  # já exclui e-mail
    materials = [p for p in passages if is_material(p.get("uri", ""))]
    pool = materials if materials else passages
    seen, picked = set(), []
    for p in pool:
        t = p.get("title", "")
        if t in seen:
            continue
        seen.add(t)
        picked.append(p)
        if len(picked) >= n:
            break
    return kb_sources(picked, snippet_len=1500)


def kb_retrieve_request(kb_id: str, query: str, n: int = 6) -> dict:
    """Monta os parâmetros exatos enviados ao Bedrock Retrieve (fonte única p/ debug)."""
    want = max(1, n)
    # Sobre-busca: alguns resultados serão de e-mail e descartados no pós-processamento.
    return {
        "knowledgeBaseId": kb_id,
        "retrievalQuery": {"text": query[:1000]},
        "retrievalConfiguration": {"vectorSearchConfiguration": {"numberOfResults": min(60, want * 2 + 6)}},
    }


def kb_retrieve(kb_client, kb_id: str, query: str, n: int = 6) -> list:
    """Recupera passagens relevantes do KB (texto + fonte S3 + página), apenas de apostilas."""
    if not kb_id or not query or kb_client is None:
        return []
    want = max(1, n)
    resp = kb_client.retrieve(**kb_retrieve_request(kb_id, query, n))
    out = []
    for r in resp.get("retrievalResults", []):
        uri = (((r.get("location") or {}).get("s3Location") or {}).get("uri") or "")
        if not is_apostila(uri):
            continue
        page = None
        raw = (r.get("metadata") or {}).get("x-amz-bedrock-kb-document-page-number")
        if raw is not None:
            try:
                page = int(float(raw))
            except (TypeError, ValueError):
                page = None
        out.append({
            "text": (r.get("content") or {}).get("text", "") or "",
            "uri": uri, "title": kb_title(uri), "page": page,
            "score": round(float(r.get("score") or 0), 4),
        })
        if len(out) >= want:
            break
    return out


def kb_sources(passages: list, snippet_len: int = 400) -> list:
    """Fontes distintas (por URI) a partir de passagens, com trecho do conteúdo."""
    seen, sources = set(), []
    for p in passages:
        uri = p.get("uri", "")
        if uri in seen:
            continue
        seen.add(uri)
        sources.append({"uri": uri, "title": p.get("title", ""),
                        "page": p.get("page"), "score": p.get("score", 0),
                        "snippet": (p.get("text", "") or "")[:snippet_len]})
    return sources


def answer_value(answers, i) -> str:
    """Lê a resposta do índice i, aceitando dict {"0":..} ou lista [..]."""
    if isinstance(answers, dict):
        return str(answers.get(str(i), answers.get(i, "")) or "")
    if isinstance(answers, list) and i < len(answers):
        return str(answers[i] or "")
    return ""


# --- Correção -------------------------------------------------------------------
# Nota: a correção NÃO acessa o KB. A sugestão de material é sob demanda (study_sources,
# chamada pelo endpoint /online-attempts/{id}/study na API).
def grade(exam: dict, answers) -> dict:
    """Corrige uma tentativa. Retorna os campos da correção (sem metadados da tentativa)."""
    if exam.get("format", "mc") == "discursive":
        return _grade_discursive(exam, answers)
    return _grade_mc(exam, answers)


def _grade_mc(exam: dict, answers) -> dict:
    questoes = exam.get("questoes") or []
    results, acertos = [], 0
    for i, q in enumerate(questoes):
        correta = str(q.get("correta", "")).strip().upper()[:1]
        marcada = answer_value(answers, i).strip().upper()[:1]
        ok = bool(marcada) and marcada == correta
        if ok:
            acertos += 1
        # Sugestão de estudo é sob demanda (endpoint separado), não na correção.
        results.append({
            "n": i + 1, "enunciado": q.get("enunciado", ""),
            "alternativas": q.get("alternativas") or [],
            "marcada": marcada, "correta": correta, "acertou": ok,
            "tema": q.get("tema", ""), "explicacao": q.get("explicacao", ""),
        })
    total = len(questoes)
    score = round((acertos / total) * 100.0, 1) if total else 0.0
    return {"format": "mc", "total": total, "acertos": acertos, "score": score,
            "results": results, "tokensIn": 0, "tokensOut": 0}


def _grade_discursive(exam: dict, answers) -> dict:
    cfg = get_model_config("exam")
    if not cfg["primaryModel"]:
        raise ValueError("Configure o modelo da capacidade 'exam' (correção discursiva).")
    questoes = exam.get("questoes") or []
    qa_pairs, gabarito = [], []
    for i, q in enumerate(questoes):
        qa_pairs.append({"question": q.get("enunciado", ""),
                         "resposta": answer_value(answers, i).strip()})
        gabarito.append({"prompt": q.get("enunciado", ""),
                         "referenceAnswer": q.get("respostaReferencia", "")})
    out = invoke_agent("exam", cfg["primaryModel"], {
        "qaPairs": qa_pairs, "strategy": "gabarito", "gabarito": gabarito,
        "maxScorePerQuestion": 10.0,
    })
    graded = (out.get("result") or {}).get("questoes") or []

    results, total_nota, total_max, acertos = [], 0.0, 0.0, 0
    for i, q in enumerate(questoes):
        g = graded[i] if i < len(graded) else {}
        try:
            nota = float(g.get("nota", 0) or 0)
        except (TypeError, ValueError):
            nota = 0.0
        try:
            nmax = float(g.get("notaMaxima", q.get("notaMaxima", 10)) or 10)
        except (TypeError, ValueError):
            nmax = 10.0
        total_nota += nota
        total_max += nmax
        passed = nmax > 0 and (nota / nmax) >= _DISC_PASS
        if passed:
            acertos += 1
        # Sugestão de estudo é sob demanda (endpoint separado), não na correção.
        results.append({
            "n": i + 1, "enunciado": q.get("enunciado", ""),
            "respostaAluno": qa_pairs[i]["resposta"],
            "respostaReferencia": q.get("respostaReferencia", ""),
            "nota": round(nota, 1), "notaMaxima": round(nmax, 1),
            "justificativa": g.get("justificativa", ""), "tema": q.get("tema", ""),
        })

    total = len(questoes)
    score = round((total_nota / total_max) * 100.0, 1) if total_max else 0.0
    usage = out.get("usage") or {}
    return {"format": "discursive", "total": total, "acertos": acertos, "score": score,
            "notaTotal": round(total_nota, 1), "notaMaxima": round(total_max, 1),
            "results": results,
            "tokensIn": int(usage.get("tokensIn", 0) or 0),
            "tokensOut": int(usage.get("tokensOut", 0) or 0)}
