"""Persistência DynamoDB do módulo LMS: catálogo (disciplinas/capítulos) e estado de
ingestão por vídeo. Thin wrapper; nomes das tabelas vêm de config (injetados pelo CDK)."""
from __future__ import annotations

from decimal import Decimal

from . import config


def to_ddb(o):
    """boto3 resource não aceita float — converte float→Decimal recursivamente."""
    if isinstance(o, float):
        return Decimal(str(o))
    if isinstance(o, list):
        return [to_ddb(x) for x in o]
    if isinstance(o, dict):
        return {k: to_ddb(v) for k, v in o.items()}
    return o


def from_ddb(o):
    """Converte Decimals de volta para int/float (JSON-serializável)."""
    if isinstance(o, list):
        return [from_ddb(x) for x in o]
    if isinstance(o, dict):
        return {k: from_ddb(v) for k, v in o.items()}
    if isinstance(o, Decimal):
        return int(o) if o == o.to_integral_value() else float(o)
    return o


class Store:
    def __init__(self, catalog_table: str | None = None, ingest_table: str | None = None,
                 region: str | None = None, resource=None):
        self.catalog_table = catalog_table or config.CATALOG_TABLE
        self.ingest_table = ingest_table or config.INGEST_TABLE
        self.region = region or config.REGION
        self._resource = resource

    @property
    def resource(self):
        if self._resource is None:
            import boto3
            self._resource = boto3.resource("dynamodb", region_name=self.region)
        return self._resource

    def _t(self, name):
        return self.resource.Table(name)

    # ---- catálogo (PK disc_id) ----
    def put_catalog(self, disc: dict) -> None:
        self._t(self.catalog_table).put_item(Item=to_ddb(disc))

    def get_catalog(self, disc_id: str) -> dict | None:
        item = self._t(self.catalog_table).get_item(Key={"disc_id": disc_id}).get("Item")
        return from_ddb(item) if item else None

    def list_catalog(self) -> list[dict]:
        items = self._t(self.catalog_table).scan().get("Items", [])
        return [from_ddb(i) for i in items]

    # ---- estado de ingestão (PK video) ----
    def set_ingest(self, video: str, status: str, **fields) -> None:
        item = {"video": video, "status": status, **fields}
        self._t(self.ingest_table).put_item(Item=to_ddb(item))

    def get_ingest(self, video: str) -> dict | None:
        item = self._t(self.ingest_table).get_item(Key={"video": video}).get("Item")
        return from_ddb(item) if item else None
