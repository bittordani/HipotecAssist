# scripts/ingest_docs.py
import os
import hashlib
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY
)

COLLECTION = "hipotecas"
VECTOR_SIZE = 384  # all-MiniLM-L6-v2
model = SentenceTransformer("all-MiniLM-L6-v2")

def ensure_collection():
    try:
        exists = client.collection_exists(COLLECTION)
        print(f"Colección '{COLLECTION}' existe: {exists}")
        if exists:
            # Borrar la colección completa para limpiar PDFs antiguos
            print("Eliminando colección existente para limpiar PDFs antiguos...")
            client.delete_collection(collection_name=COLLECTION)
            # Recrear la colección vacía
            client.recreate_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
            )
            print("Colección recreada correctamente.")
        else:
            # Crear colección si no existía
            client.recreate_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
            )
            print("Colección creada correctamente.")
    except Exception as e:
        print(f"Error comprobando o creando la colección: {e}")

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
    key = f"{origen}::{chunk_index}".encode("utf-8")
    digest = hashlib.sha1(key).digest()  # 20 bytes
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
                id=point_id,
                vector=vector.tolist() if hasattr(vector, "tolist") else vector,
                payload={
                    "texto": chunk,
                    "banco": banco,
                    "producto": producto,
                    "origen": path,
                    "chunk_index": idx,
                },
            )
        )

    try:
        client.upsert(collection_name=COLLECTION, points=points)
        print("PDF ingerido correctamente")
    except Exception as e:
        print(f"Error al subir puntos: {e}")

if __name__ == "__main__":
    print("Iniciando ingestión de PDFs...")
    ensure_collection()  # <-- borra los datos antiguos antes de ingestar
    folder_path = "data/docs_bancarios"
    for file_name in os.listdir(folder_path):
        if file_name.lower().endswith(".pdf"):
            path = os.path.join(folder_path, file_name)
            banco = "Desconocido"
            producto = "Hipoteca"
            try:
                ingest_pdf(path, banco=banco, producto=producto)
            except Exception as e:
                print(f"Error al ingerir {file_name}: {e}")


# # scripts/ingest_docs.py
# import os
# import hashlib
# from qdrant_client import QdrantClient
# from qdrant_client.models import VectorParams, Distance, PointStruct
# from sentence_transformers import SentenceTransformer
# from pypdf import PdfReader
# from dotenv import load_dotenv


# load_dotenv()

# QDRANT_URL = os.getenv("QDRANT_URL")
# QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# client = QdrantClient(
#     url=QDRANT_URL,
#     api_key=QDRANT_API_KEY
# )

# # QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
# COLLECTION = "hipotecas"
# VECTOR_SIZE = 384  # all-MiniLM-L6-v2

# # client = QdrantClient(url=QDRANT_URL)
# model = SentenceTransformer("all-MiniLM-L6-v2")


# def ensure_collection():
#     try:
#         exists = client.collection_exists(COLLECTION)
#         print(f"Colección '{COLLECTION}' existe: {exists}")
#     except Exception as e:
#         print(f"Error comprobando la colección: {e}")



# def extract_text_from_pdf(path: str) -> str:
#     reader = PdfReader(path)
#     text = ""
#     for page in reader.pages:
#         text += (page.extract_text() or "") + "\n"
#     return text


# def chunk_text(text: str, max_chars: int = 500):
#     chunks = []
#     current = ""
#     for paragraph in text.split("\n"):
#         paragraph = paragraph.strip()
#         if not paragraph:
#             continue
#         if len(current) + len(paragraph) + 1 <= max_chars:
#             current += paragraph + "\n"
#         else:
#             if current.strip():
#                 chunks.append(current.strip())
#             current = paragraph + "\n"
#     if current.strip():
#         chunks.append(current.strip())
#     return chunks


# def _stable_int_id(origen: str, chunk_index: int) -> int:
#     """
#     Genera un ID entero estable (u64) a partir de (origen + chunk_index).
#     Qdrant acepta u64 o UUID.
#     """
#     key = f"{origen}::{chunk_index}".encode("utf-8")
#     digest = hashlib.sha1(key).digest()  # 20 bytes
#     # Coge 8 bytes => u64
#     return int.from_bytes(digest[:8], byteorder="big", signed=False)


# def ingest_pdf(path: str, banco: str, producto: str):
#     print(f"Ingiere PDF: {path}")
#     text = extract_text_from_pdf(path)
#     chunks = chunk_text(text, max_chars=500)
#     print(f"Total chunks: {len(chunks)}")

#     embeddings = model.encode(chunks)
#     base_name = os.path.basename(path)

#     points = []
#     for idx, (chunk, vector) in enumerate(zip(chunks, embeddings)):
#         point_id = _stable_int_id(base_name, idx)

#         points.append(
#             PointStruct(
#                 id=point_id,  # <- ENTERO válido para Qdrant
#                 vector=vector.tolist() if hasattr(vector, "tolist") else vector,
#                 payload={
#                     "texto": chunk,
#                     "banco": banco,
#                     "producto": producto,
#                     "origen": path,     # <- el PDF bonito
#                     "chunk_index": idx,
#                 },
#             )
#         )

#     try:
#         client.upsert(collection_name=COLLECTION, points=points)
#         print("PDF ingerido correctamente")
#     except Exception as e:
#         print(f"Error al subir puntos: {e}")



# if __name__ == "__main__":
#     print("Iniciando ingestión de PDFs...")
#     ensure_collection()
#     folder_path = "data/docs_bancarios"
#     for file_name in os.listdir(folder_path):
#         if file_name.lower().endswith(".pdf"):
#             path = os.path.join(folder_path, file_name)
#             banco = "Desconocido"
#             producto = "Hipoteca"
#             try:
#                 ingest_pdf(path, banco=banco, producto=producto)
#             except Exception as e:
#                 print(f"Error al ingerir {file_name}: {e}")