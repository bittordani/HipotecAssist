from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
from google.genai import types as genai_types
from embeddings import cliente_embedding
from llm import responder_pregunta_gemini
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Conectar con Qdrant (misma config que search.py) ---
qdrant = QdrantClient(
    host="qdrant",
    port=6333
)

COLLECTION_NAME = "hipotecas"

# --- Modelo de entrada desde el frontend ---
class PreguntaUsuario(BaseModel):
    pregunta: str


@router.post("/preguntar")
def preguntar_llm(datos: PreguntaUsuario):
    try:
        pregunta = datos.pregunta.strip()

        if not pregunta:
            raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")

        # --- 1) Generar embedding de la pregunta ---
        embedding = cliente_embedding.embed_content(
            model="text-embedding-004",
            content=pregunta
        ).embeddings[0].values

        # --- 2) Recuperar contexto con Qdrant ---
        qdrant_result = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=embedding,
            limit=4
        )

        # Construimos texto RAG con los documentos recuperados
        contexto_rag = "\n\n".join(
            f"- {hit.payload.get('texto', '')}"
            for hit in qdrant_result
        )

        logger.info("🔍 Contexto RAG recuperado correctamente")

        # --- 3) Enviar al LLM (Gemini) con el contexto ---
        respuesta = responder_pregunta_gemini(
            pregunta=pregunta,
            contexto=contexto_rag
        )

        return {"respuesta": respuesta, "contexto_utilizado": contexto_rag}

    except Exception as e:
        logger.exception("❌ Error en /preguntar")
        raise HTTPException(status_code=500, detail=str(e))
