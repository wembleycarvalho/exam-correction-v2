"""Wrapper fino do Amazon S3 Vectors (serviço boto3 `s3vectors`).

Um índice de dimensão fixa (512 do Marengo 3.0), métrica cosseno, guardando 1 vetor por
(segmento × modalidade) com metadados. Ver design.md do spec lms-video.
"""
from __future__ import annotations

from . import config


def chunk(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


class VectorIndex:
    def __init__(self, bucket: str | None = None, index: str | None = None,
                 region: str | None = None, client=None):
        self.bucket = bucket or config.VECTOR_BUCKET
        self.index = index or config.VECTOR_INDEX
        self.region = region or config.REGION
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("s3vectors", region_name=self.region)
        return self._client

    def ensure_index(self, dimension: int | None = None, distance_metric: str | None = None,
                     non_filterable_keys=None) -> None:
        """Cria o índice se ainda não existir (idempotente). Dimensão/métrica/chaves
        não-filtráveis NÃO podem ser alteradas depois — definidas na criação."""
        dimension = dimension or config.EMBED_DIM
        distance_metric = distance_metric or config.DISTANCE_METRIC
        keys = list(non_filterable_keys if non_filterable_keys is not None
                    else config.NON_FILTERABLE_KEYS)
        try:
            self.client.create_index(
                vectorBucketName=self.bucket, indexName=self.index,
                dataType="float32", dimension=dimension, distanceMetric=distance_metric,
                metadataConfiguration={"nonFilterableMetadataKeys": keys})
        except Exception as e:  # noqa: BLE001
            # já existe -> ok (idempotente); qualquer outro erro propaga
            if "Conflict" in type(e).__name__ or "already exists" in str(e).lower():
                return
            # botocore ClientError com ConflictException
            code = getattr(getattr(e, "response", {}), "get", lambda *_: None)("Error")
            if isinstance(code, dict) and code.get("Code") in ("ConflictException",):
                return
            raise

    def put(self, rows: list[dict], batch_size: int = 200) -> int:
        """Insere/atualiza vetores em lote. `rows` no formato
        {key, data:{float32:[...]}, metadata:{...}}. Retorna o total inserido."""
        total = 0
        for group in chunk(rows, batch_size):
            self.client.put_vectors(vectorBucketName=self.bucket, indexName=self.index,
                                    vectors=group)
            total += len(group)
        return total

    def list_keys(self, max_total: int = 8000) -> list[str]:
        """Lista as chaves do índice (paginado, só chaves). As chaves codificam
        disc#video#start#modality, então dá pra localizar segmentos sem metadados."""
        keys, token = [], None
        while True:
            kw = {"vectorBucketName": self.bucket, "indexName": self.index,
                  "returnData": False, "returnMetadata": False, "maxResults": 500}
            if token:
                kw["nextToken"] = token
            r = self.client.list_vectors(**kw)
            keys.extend(v["key"] for v in r.get("vectors", []))
            token = r.get("nextToken")
            if not token or len(keys) >= max_total:
                break
        return keys

    def get(self, keys: list[str], return_data: bool = True,
            return_metadata: bool = True) -> list[dict]:
        resp = self.client.get_vectors(
            vectorBucketName=self.bucket, indexName=self.index, keys=keys,
            returnData=return_data, returnMetadata=return_metadata)
        return resp.get("vectors", [])

    def query(self, vector: list[float], top_k: int | None = None, flt: dict | None = None,
              return_metadata: bool = True, return_distance: bool = True) -> list[dict]:
        params = {
            "vectorBucketName": self.bucket, "indexName": self.index,
            "queryVector": {"float32": [float(x) for x in vector]},
            "topK": top_k or config.DEFAULT_TOP_K,
            "returnDistance": return_distance, "returnMetadata": return_metadata,
        }
        if flt:
            params["filter"] = flt
        resp = self.client.query_vectors(**params)
        return resp.get("vectors", [])
