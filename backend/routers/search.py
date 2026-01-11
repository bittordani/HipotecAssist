# -------------------- routers/search.py --------------------
from typing import List, Dict, Optional
from fastapi import APIRouter, Query
from qdrant_client.models import Filter, FieldCondition, MatchValue

from services.qdrant_connection import qdrant, embedding_model

# Crea un router de FastAPI para agrupar endpoints relacionados con búsqueda
router = APIRouter()


def _build_bank_filter(banco: str) -> Filter:
    # Construye un filtro de Qdrant para buscar por nombre de banco.
    b = (banco or "").strip()
    # Genera variantes del nombre para búsqueda case-insensitive
    variants = {b, b.upper(), b.lower(), b.title()}
    # Crea condiciones de matching para cada variante no vacía
    should = [FieldCondition(key="banco", match=MatchValue(value=v)) for v in variants if v]
    return Filter(should=should)


def buscar_hipotecas_en_qdrant(
    query: str,
    top_k: int = 5,
    banco: Optional[str] = None,
    min_score: float = 0.15,
) -> List[Dict]:
    # Busca documentos de hipotecas en Qdrant mediante búsqueda vectorial semántica.

    # Convierte el texto de la query a vector usando el modelo de embeddings
    vector = embedding_model.encode(query).tolist()

    # Construye filtro por banco
    q_filter = _build_bank_filter(banco) if banco else None

    # Realiza búsqueda vectorial en Qdrant
    resultados = qdrant.query_points(
        collection_name="hipotecas",
        query=vector,
        limit=top_k,
        with_payload=True,
        query_filter=q_filter,
        score_threshold=min_score,
    )

    # Procesa y formatea los resultados
    docs: List[Dict] = []
    for punto in resultados.points:
        payload = punto.payload or {}
        docs.append({
            "id": str(punto.id),
            "score": float(punto.score),
            "texto": payload.get("texto", ""),
            "banco": payload.get("banco", ""),
            "producto": payload.get("producto", ""),
            "origen": payload.get("origen", ""),        # Nombre del documento
            "ruta_pdf": payload.get("ruta_pdf", ""),   # Link al PDF
        })

    return docs


@router.get("/buscar")
def buscar(
    # para buscar documentos de hipotecas.
    
    query: str = Query(...),
    top_k: int = Query(5, ge=1, le=20),
    banco: Optional[str] = Query(None),
    min_score: float = Query(0.15, ge=0.0, le=1.0),
):
    return buscar_hipotecas_en_qdrant(query=query, top_k=top_k, banco=banco, min_score=min_score)
