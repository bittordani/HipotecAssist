# backend/llm.py
import os
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """
Eres un gestor hipotecario experto en hipotecas en España.

Dispones de:
A) ANALISIS_USUARIO: métricas calculadas del usuario
B) DOCUMENTOS_RAG: fragmentos de PDFs bancarios (FIPRE/FIPER/folletos)

REGLAS:
1) Si la pregunta pide condiciones concretas de un banco (% financiación, comisión, TIN/TAE, plazo, etc.):
   - SOLO puedes afirmar cifras/condiciones si aparecen claramente en DOCUMENTOS_RAG.
   - Si NO aparecen, NO inventes: responde como ORIENTACIÓN GENERAL sin cifras de ese banco.
2) Si usas documentos, cita SIEMPRE el ORIGEN del PDF y el ID del fragmento.
3) NO uses “DOC 1/2/3…”. No existe.
4) FORMATO OBLIGATORIO:
   - Respuesta: 2 a 6 frases
   - Fuentes: lista “<origen> (id=<id>)” o “Ninguna (no aparece en PDFs)”
"""

def _build_docs_block(documentos_rag: list) -> str:
    if not documentos_rag:
        return "NO_HAY_DOCUMENTOS"

    lines = []
    for d in documentos_rag:
        doc_id = d.get("id", "")
        banco = d.get("banco", "")
        producto = d.get("producto", "")
        origen = d.get("origen", "") or "desconocido"
        score = d.get("score", "")

        header = f"[FUENTE origen={origen} | id={doc_id} | banco={banco} | producto={producto} | score={score}]"
        body = (d.get("texto", "") or "").strip()
        lines.append(f"{header}\n{body}")

    return "\n\n".join(lines)


def responder_pregunta_gemini(
    pregunta: str,
    contexto: dict,
    documentos_rag: list,
    temperature: float = 0.2,
    max_tokens: int = 250,
) -> str:
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return "Respuesta: Error: falta GOOGLE_API_KEY en variables de entorno.\nFuentes: Ninguna (config)"

        genai.configure(api_key=api_key)

        docs_block = _build_docs_block(documentos_rag)

        prompt = f"""{SYSTEM_INSTRUCTION}

ANALISIS_USUARIO:
{contexto}

DOCUMENTOS_RAG:
{docs_block}

PREGUNTA:
{pregunta}
"""

        model = genai.GenerativeModel(model_name="gemini-2.5-flash-lite")
        resp = model.generate_content(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )

        text = (getattr(resp, "text", "") or "").strip()
        if not text:
            return "Respuesta: No he podido generar una respuesta con la información disponible.\nFuentes: Ninguna (no aparece en PDFs)"

        return text

    except Exception as e:
        logger.exception("Error en responder_pregunta_gemini")
        return f"Respuesta: Error inesperado generando respuesta.\nFuentes: Ninguna (error interno: {e})"
