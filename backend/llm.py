# backend/llm.py
import os
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Prompt del sistema para regular el comportamiento del asistente
SYSTEM_INSTRUCTION = """
Eres un asistente experto en hipotecas en España, claro, preciso y orientado a ayudar al usuario.

Dispones SIEMPRE de:
A) ANALISIS_USUARIO:
   - capital_pendiente
   - años_restantes
   - tipo_interes
   - cuota_efectiva
   - intereses_restantes
   Estos datos representan la hipoteca actual del usuario y SON VERDAD.

B) DOCUMENTOS_RAG:
   Fragmentos de PDFs bancarios oficiales (FIPRE / FIPER / folletos comerciales).
   Cada documento puede incluir:
   - origen
   - id
   - texto
   - ruta_pdf o link (si existe)

────────────────────────────────
INTENCIÓN DEL USUARIO
────────────────────────────────
Si el usuario en cualquier momento pregunta por:
- “cómo está su hipoteca”
- “si puede mejorar”
- “qué ofrecen otros bancos”
- “si puede cambiar de banco”

ENTONCES considera que la intención es:
👉 COMPARAR CON EL MERCADO
👉 BUSCAR MEJORES CONDICIONES

NO vuelvas a preguntar esto más adelante.

────────────────────────────────
REGLAS CRÍTICAS (OBLIGATORIAS)
────────────────────────────────

1) USO DEL CONTEXTO DEL USUARIO
- Si ANALISIS_USUARIO existe:
  - Usa SIEMPRE esos datos para razonar y comparar.
  - NO vuelvas a pedir capital, años, tipo o cuota.
  - NO digas que “no tienes información”.
  - NO repitas los datos al usuario salvo que sea estrictamente necesario.
  - Habla como si ya conocieras su hipoteca.

❌ Incorrecto: “No tengo información sobre tu hipoteca”
✅ Correcto: “Con las condiciones que tienes actualmente…”

2) COMPARACIÓN CON BANCOS
- Solo compara con bancos si el usuario lo pide explícita o implícitamente.
- Solo menciona cifras (TIN, TAE, plazo, etc.) si aparecen en DOCUMENTOS_RAG.
- Si no hay cifras concretas, da orientación general sin inventar números.
- Pregunta por el rango de edad para recomendar un banco u otro.

3) DOCUMENTOS Y FUENTES
- Si no hay documentos relevantes, indica:
  "Ninguna (no aparece en PDFs)"
- NUNCA digas que no puedes dar enlaces.
- Si el documento existe, asume que el sistema mostrará el enlace al usuario.


4) CAMBIO DE BANCO
- Si el usuario quiere cambiar de banco:
  - Usa directamente ANALISIS_USUARIO.
  - Solo pregunta datos adicionales si NO existen (ej: productos vinculados).
  - Una vez recopilado lo necesario:
    - Compara con DOCUMENTOS_RAG
    - Sugiere bancos que podrían mejorar sus condiciones
    - Explica brevemente por qué

5) CONVERSACIÓN NATURAL
- No seas robótico.
- No repitas frases como “para poder ayudarte…”.
- Mantén continuidad entre preguntas.
- Si el usuario ya respondió algo, asúmelo como cierto.

────────────────────────────────
FORMATO OBLIGATORIO DE RESPUESTA
────────────────────────────────

Respuesta:
- 1 a 3 frases
- Clara, directa y útil
- Enfocada en resolver la pregunta concreta


────────────────────────────────
OBJETIVO FINAL
────────────────────────────────
Ayudar al usuario a:
- Entender si su hipoteca es buena o mejorable
- Saber qué bancos ofrecen mejores condiciones
- Tomar decisiones informadas sin confusión
- Sentir que el asistente recuerda su situación y le acompaña
"""
# Fuentes:
# - Lista de documentos usados:
#   "<origen> (id=<id>)"
# - O bien:
#   "Ninguna (no aparece en PDFs)"



def _build_docs_block(documentos_rag: list) -> str:
    """
    Convierte la lista de documentos RAG en un bloque de texto formateado
    con enlaces clicables a los PDFs fuente.
    
    Args:
        documentos_rag: Lista de diccionarios con info de documentos recuperados
                       Cada documento incluye: texto, ruta_pdf, id, origen
    
    Returns:
        String formateado con los documentos y sus fuentes, o mensaje
        indicando que no hay documentos disponibles
    """
    if not documentos_rag:
        return "Ninguna (no aparece en PDFs)"

    lines = []
    for d in documentos_rag:
        texto = (d.get("texto") or "").strip()
        pdf = d.get("ruta_pdf")
        doc_id = d.get("id", "")

        if pdf:
            # Extrae solo el nombre del archivo del path completo
            filename = os.path.basename(pdf)
            # Link clicable para HTML
            lines.append(f"{texto} (Fuente: <a href='/pdfs/{filename}' target='_blank'>{filename}</a>, id={doc_id})")
        else:
            # Si no hay PDF, usa el campo 'origen' como referencia
            origen = d.get("origen") or "desconocido"
            filename = os.path.basename(origen.replace("\\", "/"))
            lines.append(f"{texto} (Fuente: {filename}, id={doc_id})")

    return "\n\n".join(lines)







def resumir_contexto_usuario_natural(contexto: dict) -> str:
    """
    Devuelve un resumen conversacional de la hipoteca del usuario
    para que el LLM pueda usarlo de manera natural.
    """
    if not contexto:
        return "No hay datos de hipoteca del usuario."

    # Extrae datos de entrada originales del usuario
    entrada = contexto.get("entrada", {})
    # Extrae métricas calculadas por el sistema
    metricas = contexto.get("metricas", {})

    capital = entrada.get("capital_pendiente")
    anos = entrada.get("anos_restantes")
    tipo = entrada.get("tipo")
    cuota = metricas.get("cuota_efectiva")
    intereses = metricas.get("intereses_restantes_aprox")

    # Construye resumen conversacional con los datos clave
    resumen = (
        f"Tienes una hipoteca de {capital} € con {anos} años restantes, "
        f"tipo {tipo}. Tu cuota mensual efectiva es de aproximadamente {cuota} €, "
        f"y los intereses que te quedan por pagar se estiman en {intereses} €."
    )

    # Añade avisos financieros si el sistema los ha generado
    avisos = contexto.get("avisos", [])
    if avisos:
        resumen += " Además, considera lo siguiente: " + "; ".join(avisos)

    return resumen

# -------------------- Función principal --------------------
def responder_pregunta_gemini(
    pregunta: str,
    contexto: dict,
    documentos_rag: list,
    temperature: float = 0.2,
    max_tokens: int = 250,
) -> str:
    """
    Genera una respuesta usando Gemini basada en la pregunta del usuario,
    su contexto hipotecario y documentos RAG relevantes.
    """
    try:
        # Verifica que exista la API key de Google
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return "Respuesta: Error: falta GOOGLE_API_KEY en variables de entorno.\nFuentes: Ninguna (config)"

        # Configura cliente de Gemini
        genai.configure(api_key=api_key)

        # Prepara los bloques de contexto para el prompt
        docs_block = _build_docs_block(documentos_rag)
        contexto_resumido = resumir_contexto_usuario_natural(contexto)

        # Construye el prompt completo con instrucciones, contexto y pregunta
        prompt = f"""{SYSTEM_INSTRUCTION}

ANALISIS_USUARIO:
{contexto_resumido}

DOCUMENTOS_RAG:
{docs_block}

PREGUNTA:
{pregunta}
"""

        # Inicializa modelo
        model = genai.GenerativeModel(model_name="gemini-2.5-flash-lite")

        # Genera respuesta con configuración específica
        resp = model.generate_content(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )

        # Extrae texto de la respuesta
        text = (getattr(resp, "text", "") or "").strip()
        if not text:
            return "Respuesta: No he podido generar una respuesta con la información disponible.\nFuentes: Ninguna (no aparece en PDFs)"

        return text

    except Exception as e:
        # Registra error completo en logs y devuelve mensaje de error al usuario
        logger.exception("Error en responder_pregunta_gemini")
        return f"Respuesta: Error inesperado generando respuesta.\nFuentes: Ninguna (error interno: {e})"
