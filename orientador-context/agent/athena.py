"""Helper de consulta ao data lake (Glue catalog `moodle_datalake`) via Athena.

Endpoints públicos (Athena/Glue/S3) — sem VPC. Roda uma query e devolve linhas como dicts.
"""
import os
import time

import boto3

_athena = boto3.client("athena")

GLUE_DB = os.environ.get("GLUE_DB", "moodle_datalake")
WORKGROUP = os.environ.get("WORKGROUP", "moodle-datalake")


def query(sql: str, max_wait: float = 25.0, max_results: int = 200):
    """Executa `sql` no workgroup do data lake e retorna List[dict] (cabeçalho = 1ª linha)."""
    qid = _athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": GLUE_DB},
        WorkGroup=WORKGROUP,
    )["QueryExecutionId"]

    deadline = time.time() + max_wait
    state = "QUEUED"
    while time.time() < deadline:
        state = _athena.get_query_execution(
            QueryExecutionId=qid)["QueryExecution"]["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(0.6)

    if state != "SUCCEEDED":
        raise RuntimeError(f"Athena {state}")

    res = _athena.get_query_results(QueryExecutionId=qid, MaxResults=max_results)
    rows = res["ResultSet"]["Rows"]
    if not rows:
        return []
    header = [c.get("VarCharValue", "") for c in rows[0]["Data"]]
    out = []
    for r in rows[1:]:
        vals = [c.get("VarCharValue") for c in r["Data"]]
        out.append(dict(zip(header, vals)))
    return out
