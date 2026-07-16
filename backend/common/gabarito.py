"""Helper compartilhado: recuperar gabarito versionado da tabela `exams`.

Usado pelo worker (estratégia 'gabarito') sem hop de Lambda extra.
"""
import boto3
from boto3.dynamodb.conditions import Key


def get_gabarito(exams_table_name: str, exam_id: str, version: str = "") -> dict:
    table = boto3.resource("dynamodb").Table(exams_table_name)
    if version:
        item = table.get_item(Key={"examId": exam_id, "version": str(version)}).get("Item")
    else:
        resp = table.query(
            KeyConditionExpression=Key("examId").eq(exam_id),
            ScanIndexForward=False,
            Limit=1,
        )
        items = resp.get("Items", [])
        item = items[0] if items else None
    if not item:
        return {"found": False, "examId": exam_id}
    return {
        "found": True,
        "examId": exam_id,
        "version": item.get("version"),
        "questions": item.get("questions", []),
    }
