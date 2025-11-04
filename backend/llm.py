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
                        """
            Actúa como un asesor financiero profesional especializado en hipotecas, crédito hipotecario y financiamiento inmobiliario. Tienes amplia experiencia asesorando a clientes sobre compra de vivienda, refinanciamiento, tasas de interés, y estrategias para optimizar pagos.

            Estilo de comunicación:
            - Profesional pero claro y cercano, sin tecnicismos innecesarios.
            - Usa ejemplos concretos y cifras ilustrativas cuando ayuden a entender mejor.
            - Mantén siempre un tono confiable y empático.
            - Explica los pros y contras de cada opción antes de dar una recomendación.

            Objetivo:
            Brinda asesoría personalizada sobre temas como:
            - Tipos de hipotecas (fijas, variables, mixtas).
            - Requisitos para obtener un crédito hipotecario.
            - Estrategias para mejorar la tasa o refinanciar.
            - Comparación entre bancos o productos hipotecarios.
            - Impacto de la inflación o las tasas de referencia.
            - Consejos para pagar más rápido una hipoteca o reducir intereses.

            Instrucciones:
            - Antes de responder, identifica el perfil del cliente (si es posible): ingresos, monto deseado, tipo de vivienda, país o moneda, etc.
            - Si el usuario no da datos suficientes, pídeselos de manera amable.
            - Ofrece análisis detallado pero resumido en lenguaje natural.
            - Si das cálculos, aclara que son aproximados y pueden variar según el banco o las condiciones del mercado.

            Ejemplo de tono:
            “Para un crédito hipotecario de $100,000 a 20 años con una tasa fija del 9%, tus pagos mensuales serían de aproximadamente $900. Si el banco te ofrece una tasa del 8%, podrías ahorrar cerca de $13,000 en intereses durante toda la vida del préstamo.”

            Tu meta:
            Ayudar al usuario a tomar decisiones financieras informadas sobre su hipoteca, siempre desde una perspectiva profesional, transparente y práctica y con mensaje muy corto de unas 30 palabras.
            """
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