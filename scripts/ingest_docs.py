# scripts/ingest_docs.py
import os
import hashlib
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = "hipotecas"
VECTOR_SIZE = 384  # all-MiniLM-L6-v2

client = QdrantClient(url=QDRANT_URL)
model = SentenceTransformer("all-MiniLM-L6-v2")


def ensure_collection():
    # Crear si no existe; si existe, la borramos y la recreamos (para demo/ingesta limpia)
    if client.collection_exists(COLLECTION):
        client.delete_collection(collection_name=COLLECTION)

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    print(f"Colección '{COLLECTION}' creada correctamente")


def extract_text_from_pdf(path: str) -> str:
    reader = PdfReader(path)
    text = ""
    for page in reader.pages:
        text += (page.extract_text() or "") + "\n"
    return text


def chunk_text(text: str, max_chars: int = 500):
    chunks = []
    current = ""
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(current) + len(paragraph) + 1 <= max_chars:
            current += paragraph + "\n"
        else:
            if current.strip():
                chunks.append(current.strip())
            current = paragraph + "\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _stable_int_id(origen: str, chunk_index: int) -> int:
    """
    Genera un ID entero estable (u64) a partir de (origen + chunk_index).
    Qdrant acepta u64 o UUID.
    """
    key = f"{origen}::{chunk_index}".encode("utf-8")
    digest = hashlib.sha1(key).digest()  # 20 bytes
    # Coge 8 bytes => u64
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def ingest_pdf(path: str, banco: str, producto: str):
    print(f"Ingiere PDF: {path}")
    text = extract_text_from_pdf(path)
    chunks = chunk_text(text, max_chars=500)
    print(f"Total chunks: {len(chunks)}")

    embeddings = model.encode(chunks)
    base_name = os.path.basename(path)

    points = []
    for idx, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        point_id = _stable_int_id(base_name, idx)

        points.append(
            PointStruct(
                id=point_id,  # <- ENTERO válido para Qdrant
                vector=vector.tolist() if hasattr(vector, "tolist") else vector,
                payload={
                    "texto": chunk,
                    "banco": banco,
                    "producto": producto,
                    "origen": base_name,     # <- el PDF bonito
                    "chunk_index": idx,
                },
            )
        )

    client.upsert(collection_name=COLLECTION, points=points)
    print("PDF ingerido correctamente")


if __name__ == "__main__":
    ensure_collection()

    pdfs = [
        ("data/docs_bancarios/FIPRE_BBVA.pdf", "BBVA", "Variable"),
        ("data/docs_bancarios/FIPRE_ING.pdf", "ING", "Fija"),
        ("data/docs_bancarios/FIPRE_SANTANDER.pdf", "Santander", "Mixta"),
    ]

    for ruta, banco, producto in pdfs:
        ingest_pdf(ruta, banco=banco, producto=producto)
