#!/usr/bin/env python3
"""CLI de demonstração do Orientador Acadêmico (sem Streamlit).

Uso:
  python demo.py stats
  python demo.py progress student_002
  python demo.py recommend student_002 [career_002]
  python demo.py ask student_002 "Quero trabalhar com IA, o que curso agora?" [--llm]
  python demo.py whatif disc_008
  python demo.py compare career_001 career_002

Com --llm (ou env ORIENTADOR_USE_LLM=1), usa o Amazon Bedrock para interpretar a
pergunta e reescrever a resposta; sem isso, roda 100% offline (fallback determinístico).
"""
import json
import sys

from src.graph.builder import build_graph
from src.graph import queries as q
from src.recommender import path_engine as pe


def _pp(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv):
    if not argv:
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    g = build_graph()

    if cmd == "stats":
        _pp(q.graph_stats(g))
    elif cmd == "progress":
        _pp(pe.student_progress(g, args[0]))
    elif cmd == "recommend":
        career = args[1] if len(args) > 1 else None
        _pp(pe.recommend_path(g, args[0], career))
    elif cmd == "whatif":
        _pp(pe.what_if_skip(g, args[0]))
    elif cmd == "compare":
        _pp(pe.compare_careers(g, args[0], args[1]))
    elif cmd == "ask":
        student_id = args[0]
        use_llm = "--llm" in args
        question = " ".join(a for a in args[1:] if a != "--llm")
        from src.llm.response_builder import answer_question
        llm = None
        if use_llm:
            from src.llm.bedrock_client import BedrockLLM
            llm = BedrockLLM()
        r = answer_question(g, student_id, question, llm=llm, polish=use_llm)
        print(r["answer"])
        print("\n[intent=%s | source=%s]" % (r["intent"], r["intent_source"]))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
