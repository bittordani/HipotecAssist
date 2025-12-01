import os
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")

qdrant = QdrantClient(url=QDRANT_URL)
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")




def recuperar_contexto(query: str, k: int = 5) -> str:
    # 1. Embedding de la pregunta del usuario
    vector = embedding_model.encode(query).tolist()

    # 2. Búsqueda en Qdrant
    resp = qdrant.query_points(
        collection_name="hipotecas",
        query=vector,
        limit=k,
        with_payload=True,
    )

    # 3. Juntar los textos de los documentos
    trozos = []
    for p in resp.points:
        payload = p.payload or {}
        texto = payload.get("texto")
        if texto:
            trozos.append(texto)

    contexto = "\n\n---\n\n".join(trozos)
    return contexto
