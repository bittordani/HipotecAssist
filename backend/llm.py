# llm.py
import os
import getpass
import logging
import sys

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

# -------------------- Logging para Docker --------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# -------------------- Cargar .env --------------------
load_dotenv()

# -------------------- Pedir API Key si no está --------------------
if not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = getpass.getpass("🔑 Google Gemini API Key: ")
    logger.info("✅ Clave GOOGLE_API_KEY asignada desde input.")
else:
    logger.info("✅ Clave GOOGLE_API_KEY cargada desde variables de entorno.")

# -------------------- Inicializar cliente Gemini --------------------
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# -------------------- Función principal para responder preguntas --------------------
def responder_pregunta_gemini(
    pregunta: str,
    contexto: dict,
    temperature: float = 0.3,
    max_tokens: int = 250
):
    """
    Envía la pregunta al modelo Gemini usando el contexto del análisis previo.
    Devuelve la respuesta de texto.
    """
    try:
        # Convertimos el contexto en un resumen legible
        contexto_texto = f"Contexto del usuario: {contexto}" if contexto else ""
        system_instruction = (
            "Eres un asistente hipotecario experto en hipotecas en España. "
            "Tu objetivo es ayudar al usuario a entender su situación hipotecaria, cuotas, intereses, DTI o LTV. "
            "Responde SIEMPRE en español, de forma breve y clara (1 a 3 frases), con tono empático y profesional."
        )

        # Creamos el chat
        chat = client.chats.create(model="gemini-2.5-flash-lite")

        # Enviar mensaje inicial con contexto
        first_response = chat.send_message(
            f"{system_instruction}\n{contexto_texto}\nPregunta del usuario: {pregunta}"
        )

        logger.info("✅ Respuesta Gemini obtenida correctamente")
        return first_response.text

    except Exception as e:
        logger.exception("Error en responder_pregunta_gemini")
        return f"Error inesperado en Gemini: {e}"