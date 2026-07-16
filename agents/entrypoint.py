"""Entrypoint do AgentCore Runtime.

Um único Runtime hospeda os agentes especialistas; o `capability` no payload roteia para o
agente certo. Invocado pelo worker (e pelo wizard da API) via `InvokeAgentRuntime`.

Payload:  {"capability": "transcription|essay|exam|author", "modelId": "...", "input": {...}}
Resposta: {"ok": true, "result": {...}, "usage": {...}, "model": "..."}  (ou ok:false + error)
"""
from bedrock_agentcore.runtime import BedrockAgentCoreApp

import specialists

app = BedrockAgentCoreApp()


def _dispatch(payload: dict) -> dict:
    capability = (payload or {}).get("capability", "")
    model_id = (payload or {}).get("modelId", "")
    data = (payload or {}).get("input", {}) or {}

    if capability == "transcription":
        return specialists.run_transcription(
            model_id, data.get("imageB64", ""), data.get("ext", "png"),
            data.get("kind", "essay"),
        )
    if capability == "essay":
        return specialists.run_essay(model_id, data.get("essayText", ""), data.get("rubric", {}))
    if capability == "exam":
        return specialists.run_exam(
            model_id, data.get("qaPairs", []), data.get("strategy", "model"),
            data.get("gabarito"), float(data.get("maxScorePerQuestion", 10.0)),
        )
    if capability == "author":
        return specialists.run_author(model_id, data.get("question", ""))
    if capability == "answersheet":
        return specialists.run_answersheet(
            model_id, data.get("imageB64", ""), data.get("ext", "png"),
            data.get("expected"),
        )
    if capability == "judge":
        return specialists.run_judge(
            model_id, data.get("kind", "essay"),
            data.get("candidateA", ""), data.get("candidateB", ""),
            data.get("context", ""),
        )
    raise ValueError(f"capability desconhecida: {capability!r}")


@app.entrypoint
def invoke(payload: dict) -> dict:
    try:
        out = _dispatch(payload)
        return {"ok": True, **out}
    except Exception as exc:  # noqa: BLE001 — contrato de erro estruturado
        return {"ok": False, "error": str(exc)}


if __name__ == "__main__":
    app.run()
