"""Auto-avaliação da busca (sem curadoria manual).

Usa cada capítulo como consulta (seu texto narrado/título) e verifica se o trecho retornado
cai na janela de tempo daquele capítulo (acerto de timestamp) e na disciplina certa. Como
temos o ground-truth (manifesto), dá pra medir precision@1, hit@k e discipline@1.

`search_fn(query, disc_id) -> list[hit_dict]` é injetado (na prática, a busca por texto).
Funções puras — testáveis sem AWS.
"""
from __future__ import annotations


def overlaps(a_start: float, a_end: float, b_start: float, b_end: float, tol: float = 0.0) -> bool:
    """True se [a_start,a_end] intercepta [b_start,b_end] (com tolerância)."""
    return a_start < b_end + tol and b_start - tol < a_end


def is_correct(hit: dict, disc_id: str, chapter: dict, tol: float = 0.5) -> bool:
    """Hit correto = mesma disciplina E o CENTRO do segmento cai na janela do capítulo
    (mesma regra do casamento segmento↔capítulo na ingestão). Tolerância pequena evita
    que capítulos adjacentes sejam confundidos."""
    if hit.get("disc_id") != disc_id:
        return False
    ch_start = float(chapter.get("start_sec", 0))
    ch_end = ch_start + float(chapter.get("dur_sec", 0))
    center = (float(hit.get("start_sec", 0)) + float(hit.get("end_sec", 0))) / 2.0
    return (ch_start - tol) <= center < (ch_end + tol)


def evaluate(disciplines: list[dict], search_fn, k: int = 5, tol: float = 0.5,
             verbose: bool = False) -> dict:
    total = hit1 = hitk = disc1 = 0
    per_query = []
    for d in disciplines:
        did = d["disc_id"]
        for ch in d.get("chapters", []):
            query = ch.get("narration") or ch.get("title") or ""
            results = search_fn(query, did) or []
            total += 1
            top = results[0] if results else None
            c1 = bool(top) and is_correct(top, did, ch, tol)
            ck = any(is_correct(r, did, ch, tol) for r in results[:k])
            d1 = bool(top) and top.get("disc_id") == did
            hit1 += int(c1); hitk += int(ck); disc1 += int(d1)
            if verbose:
                per_query.append({"disc_id": did, "chapter_index": ch.get("index"),
                                  "query": query, "hit1": c1, "hitk": ck, "disc1": d1})

    def pct(x):
        return round(x / total, 4) if total else 0.0

    report = {"total": total, "k": k, "tolerance_sec": tol,
              "precision_at_1": pct(hit1), "hit_at_k": pct(hitk),
              "discipline_at_1": pct(disc1)}
    if verbose:
        report["per_query"] = per_query
    return report
