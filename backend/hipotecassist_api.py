# backend/hipotecassist_api.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from math import pow
from typing import Optional, List, Dict
import logging
from logging.handlers import RotatingFileHandler
import time
import os
import re
from datetime import datetime

from pathlib import Path
from routers.search import router as search_router
from routers.search import buscar_hipotecas_en_qdrant
from llm import responder_pregunta_gemini

# -------------------- Estado global --------------------
# Almacena el último análisis de hipoteca realizado
# Se usa para mantener contexto entre /analisis y /preguntar
ultimo_resultado: Optional[Dict] = None

# --- Carpeta logs relativa al archivo principal ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Nombre único por sesión
session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = os.path.join(LOG_DIR, f"app_{session_id}.log")

# ----------------------------
# Configurar logging
# ----------------------------
# Limpiar handlers previos
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Crear handler de archivo con rotación
file_handler = RotatingFileHandler(
    log_path,
    maxBytes=10 * 1024 * 1024,  # 10 MB por archivo
    backupCount=30,
    encoding="utf-8"
)

# Formato de logs
formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    "%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)

# Configuración global
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, logging.StreamHandler()]  # logs a archivo y consola
)

logger = logging.getLogger(__name__)
logger.info(f"🟢 FastAPI iniciada. Logs en: {log_path}")

# -------------------- App --------------------
app = FastAPI()

# Incluye router de búsqueda
app.include_router(search_router)

# Monta directorio estático para servir PDFs
app.mount("/pdfs", StaticFiles(directory="data/docs_bancarios"), name="pdfs")

# Configuración CORS para permitir peticiones desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- Utilidades de cálculo --------------------
def cuota_mensual(P: float, rate_annual: float, n_months: int) -> float:
    # Calcula la cuota mensual de un préstamo usando la fórmula francesa.

    r = rate_annual / 12.0 # Convierte tipo anual a mensual
    if r <= 0:
        # Si no hay interés, amortización lineal
        return P / n_months
    return P * (r * pow(1 + r, n_months)) / (pow(1 + r, n_months) - 1)

def intereses_restantes_aprox(P: float, rate_annual: float, n_months: int) -> float:
    #Calcula aproximadamente los intereses totales pendientes de pagar.

    c = cuota_mensual(P, rate_annual, n_months)
    total = c * n_months
    return max(0.0, total - P)

def resumen_amortizacion(P: float, rate_annual: float, n_months: int, hitos=(12, 60, 120)) -> List[Dict]:
    # Genera tabla de amortización mostrando el estado en meses específicos.

    r = rate_annual / 12.0
    c = cuota_mensual(P, rate_annual, n_months)
    bal = P # Saldo pendiente
    interes_acum = 0.0
    out = []
    # Incluye siempre el último mes además de los hitos definidos
    setpoints = set(hitos) | {n_months}

    for m in range(1, n_months + 1):
        i = bal * r # Interés del mes actual
        p = c - i # Amortización de capital
        bal = max(0.0, bal - p) # Nuevo saldo
        interes_acum += i

        # Solo guarda información en los meses de interés
        if m in setpoints:
            out.append({
                "mes": m,
                "cuota": round(c, 2),
                "interes_mes": round(i, 2),
                "amortizado_mes": round(p, 2),
                "saldo": round(bal, 2),
                "interes_acum": round(interes_acum, 2),
            })
        # Termina iteración si ya está completamente pagado
        if bal <= 0:
            break

    return out

def ahorro_amortizacion_extra(P: float, rate_annual: float, n_months: int, extra: float, when_month: int = 1) -> float:
    #Calcula el ahorro en intereses al hacer una amortización anticipada.

    r = rate_annual / 12.0
    c = cuota_mensual(P, rate_annual, n_months)

    # SIN amortización extra
    b = P
    total_i_no = 0.0
    for _ in range(1, n_months + 1):
        i = b * r
        total_i_no += i
        b = max(0.0, b - (c - i))
        if b <= 0:
            break

    # CON amortización extra
    b = P
    total_i_si = 0.0
    for m in range(1, n_months + 1):
        i = b * r
        # Aplica la amortización extra en el mes indicado
        if m == when_month:
            b = max(0.0, b - extra)

        # Calcula el pago del mes
        pay = c if b + i > c else (b + i)
        total_i_si += min(i, pay)
        b = max(0.0, b - (pay - i))
        if b <= 0:
            break
    # Devuelve la diferencia (ahorro)
    return round(max(0.0, total_i_no - total_i_si), 2)

def stress_test_cuota(P: float, rate_annual: float, n_months: int, deltas=(0.01, 0.02)):
    # Simula incrementos del tipo de interés para evaluar impacto en la cuota.
    base = cuota_mensual(P, rate_annual, n_months)
    res = []
    for d in deltas:
        r2 = max(0.0, rate_annual + d) # Tipo con incremento
        c2 = cuota_mensual(P, r2, n_months) # Cuota con nuevo tipo
        res.append({
            "delta_tipo_pp": int(d * 100), # Delta en puntos porcentuales
            "tipo_resultante": round((r2 * 100), 3), # Tipo resultante en %
            "cuota": round(c2, 2),
            "diferencia": round(c2 - base, 2), # Incremento de cuota
        })
    return round(base, 2), res

def calcula_dti(cuota: float, ingresos_mensuales: Optional[float]) -> Optional[float]:
    """
    Calcula el ratio Debt-to-Income (DTI): % de ingresos destinado a pagar deuda.
    
    Valores de referencia:
    - <35%: Saludable
    - 35-40%: En el límite
    - >40%: Sobreendeudamiento
    """
    if not ingresos_mensuales or ingresos_mensuales <= 0:
        return None
    return round((cuota / ingresos_mensuales) * 100.0, 2)

def calcula_ltv(capital_pendiente: float, valor_vivienda: Optional[float]) -> Optional[float]:
    """
    Calcula el ratio Loan-to-Value (LTV): % del valor de la vivienda que está financiado.
    
    Valores de referencia:
    - <70%: Bajo riesgo
    - 70-80%: Riesgo moderado
    - >80%: Alto apalancamiento
    """
    if not valor_vivienda or valor_vivienda <= 0:
        return None
    return round((capital_pendiente / valor_vivienda) * 100.0, 2)

# -------------------- Modelos --------------------
class AnalisisInput(BaseModel):
    # Datos obligatorios
    capital_pendiente: float = Field(..., gt=0)
    anos_restantes: int = Field(..., gt=0)
    tipo: str = Field("fijo", description="fijo | variable")

    # Para hipoteca FIJA
    tin: Optional[float] = None

    # Para hipoteca VARIABLE
    euribor: Optional[float] = None
    diferencial: Optional[float] = None

    # Datos opcionales para cálculos avanzados
    cuota_actual: Optional[float] = None
    ingresos_mensuales: Optional[float] = None
    otras_deudas_mensuales: Optional[float] = 0.0
    valor_vivienda: Optional[float] = None

    # Para comparar con ofertas de subrogación
    oferta_alternativa_tin: Optional[float] = None

class PreguntaInput(BaseModel):
    # Modelo para realizar preguntas al LLM sobre el análisis de hipoteca.

    pregunta: str
    temperature: float = 0.2
    max_tokens: int = 250

# -------------------- Middleware logging --------------------
@app.middleware("http")
async def simple_logger(request: Request, call_next):
    # Para monitorización y debug

    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration:.2f}s)")
    return response

# -------------------- Básicos --------------------
@app.get("/")
def root():
    #Verificar que la API está activa
    logger.info("API activa CORRECTAMENTE")
    return {"ok": True, "msg": "API de análisis hipotecario activa"}

# Para el track del uptime
start_time = datetime.utcnow()

@app.get("/health")
def health_check():
    # muestra el tiempo de actividad del servidor.
    uptime = datetime.utcnow() - start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_formatted = f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
    return {"status": "ok", "uptime": uptime_formatted}

# -------------------- /analisis --------------------
@app.post("/analisis")
def analisis(data: AnalisisInput):
    # analiza una hipoteca y calcula todas las métricas.

    global ultimo_resultado

    logger.info(f"Analizando hipoteca: tipo={data.tipo}, capital={data.capital_pendiente}, años={data.anos_restantes}")

    P = data.capital_pendiente
    n_meses = data.anos_restantes * 12

    # Determina el tipo de interés según tipo de hipoteca
    if data.tipo.lower() == "variable":
        # Hipoteca variable: Euríbor + diferencial
        if data.euribor is None or data.diferencial is None:
            logger.warning("Faltan euribor o diferencial para hipoteca variable")
            return {"ok": False, "error": "Para 'variable' necesitas euribor y diferencial."}
        tipo_anual = (data.euribor + data.diferencial) / 100.0
        tipo_label = f"variable (Euríbor {data.euribor:.2f}% + {data.diferencial:.2f}%)"
    else:
        # Hipoteca fija: TIN directo
        if data.tin is None:
            logger.warning("Falta TIN para hipoteca fija")
            return {"ok": False, "error": "Para 'fijo' necesitas el TIN (%)."}
        tipo_anual = data.tin / 100.0
        tipo_label = f"fijo ({data.tin:.2f}%)"

    # Calcula cuota estimada y usa la real si está disponible
    cuota_estimada = cuota_mensual(P, tipo_anual, n_meses)
    cuota_efectiva = data.cuota_actual or cuota_estimada

    # Calcula intereses totales restantes
    intereses_totales = intereses_restantes_aprox(P, tipo_anual, n_meses)

    # Genera tabla de amortización en puntos clave (años 1, 5, 10)
    resumen = resumen_amortizacion(P, tipo_anual, n_meses, hitos=(12, 60, 120))

    # Calcula ratios financieros (DTI y LTV)
    dti = calcula_dti(cuota_efectiva + (data.otras_deudas_mensuales or 0.0), data.ingresos_mensuales)
    ltv = calcula_ltv(P, data.valor_vivienda)

    # Stress test: simula subidas de +1% y +2%
    cuota_base, stress = stress_test_cuota(P, tipo_anual, n_meses, deltas=(0.01, 0.02))

    # Calcula ahorro por amortizaciones anticipadas de 1k, 5k y 10k
    ahorro_1k = ahorro_amortizacion_extra(P, tipo_anual, n_meses, 1000.0, 1)
    ahorro_5k = ahorro_amortizacion_extra(P, tipo_anual, n_meses, 5000.0, 1)
    ahorro_10k = ahorro_amortizacion_extra(P, tipo_anual, n_meses, 10000.0, 1)

    # Comparativa con oferta alternativa (si existe)
    comparativa = None
    if data.oferta_alternativa_tin:
        alt_rate = data.oferta_alternativa_tin / 100.0
        cuota_alt = cuota_mensual(P, alt_rate, n_meses)
        interes_alt = intereses_restantes_aprox(P, alt_rate, n_meses)
        comparativa = {
            "tin_alternativo": round(data.oferta_alternativa_tin, 3),
            "cuota_alternativa": round(cuota_alt, 2),
            "diferencia_cuota": round(cuota_alt - cuota_base, 2),
            "intereses_alternativos": round(interes_alt, 2),
            "ahorro_intereses": round(intereses_totales - interes_alt, 2),
        }

    # Genera avisos basados en DTI y LTV
    avisos = []
    if dti is not None:
        if dti >= 40:
            avisos.append("DTI alto (>40%): riesgo de sobreendeudamiento.")
        elif dti >= 35:
            avisos.append("DTI moderado (35–40%): vigila tu colchón financiero.")
    if ltv is not None:
        if ltv > 80:
            avisos.append("LTV >80%: alto apalancamiento; la subrogación puede ser más difícil.")
        elif ltv > 70:
            avisos.append("LTV 70–80%: margen razonable, pero cuidado con caídas de valor.")

    # Construye respuesta completa con todas las métricas
    resultado = {
        "ok": True,
        "entrada": {"capital_pendiente": P, "anos_restantes": data.anos_restantes, "tipo": tipo_label},
        "metricas": {
            "cuota_efectiva": round(cuota_efectiva, 2),
            "cuota_estimada": round(cuota_estimada, 2),
            "intereses_restantes_aprox": round(intereses_totales, 2),
            "dti": dti,
            "ltv": ltv,
        },
        "stress_test": {"cuota_base": cuota_base, "escenarios": stress},
        "amortizacion_extra": {"ahorro_1k": ahorro_1k, "ahorro_5k": ahorro_5k, "ahorro_10k": ahorro_10k},
        "resumen_amortizacion": resumen,
        "comparativa_subrogacion": comparativa,
        "avisos": avisos,
    }

    ultimo_resultado = resultado
    logger.info("Análisis completado CORRECTAMENTE")
    return resultado

# # -------------------- Helpers --------------------
# def detectar_banco_desde_texto(texto: str) -> Optional[str]:
#     t = (texto or "").lower()
#     if "ing" in t:
#         return "ING"
#     if "santander" in t:
#         return "Santander"
#     if "bbva" in t:
#         return "BBVA"
#     return None

# -------------------- /preguntar --------------------
# @app.post("/preguntar")
# def preguntar(body: PreguntaInput):
#     global ultimo_resultado

#     if not ultimo_resultado:
#         logger.warning("Intento de /preguntar sin análisis previo")
#         return {"ok": False, "error": "No hay análisis previo. Envía el formulario primero."}

#     banco = detectar_banco_desde_texto(body.pregunta)

#     # RAG directo (sin requests a localhost, evita líos en Docker)
#     docs_rag = buscar_hipotecas_en_qdrant(
#         query=body.pregunta,
#         top_k=5,
#         banco=None,
#         min_score=0.15,
#     )
#     logger.info(f"/preguntar: RAG docs={len(docs_rag)} banco_filtro={banco}")

#     respuesta = responder_pregunta_gemini(
#         pregunta=body.pregunta,
#         contexto=ultimo_resultado,
#         documentos_rag=docs_rag,
#         temperature=body.temperature,
#         max_tokens=body.max_tokens,
#     )

#     return {"ok": True, "respuesta": respuesta, "documentos_usados": docs_rag}

# def extraer_pdfs_usados(texto_respuesta: str) -> set:
#     # Busca solo el bloque de fuentes después de "Fuentes usadas:"
#     match = re.search(r"Fuentes usadas:\s*(.*)", texto_respuesta)
#     if match:
#         return set([x.strip() for x in match.group(1).split(",") if x.strip()])
#     return set()


# @app.post("/preguntar")
# def preguntar_llm(datos: PreguntaInput):
#     logger.info(f"/preguntar recibida: '{datos.pregunta[:50]}...'")
    
#     if not datos.pregunta.strip():
#         logger.warning("Pregunta vacía recibida en /preguntar")
#         raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")
#     if not ultimo_resultado:
#         logger.warning("Intento de /preguntar sin análisis previo")
#         raise HTTPException(status_code=400, detail="No hay análisis previo. Envía el formulario primero.")

#     # RAG: buscar documentos relevantes
#     docs_rag = buscar_hipotecas_en_qdrant(
#         query=datos.pregunta,
#         top_k=5,
#         min_score=0.15
#     )

#     # Construir rutas de PDF si faltan
#     for d in docs_rag:
#         if not d.get("ruta_pdf") and d.get("origen"):
#             d["ruta_pdf"] = d["origen"].replace("\\", "/")

#     # Llamada al LLM
#     respuesta = responder_pregunta_gemini(
#         pregunta=datos.pregunta,
#         contexto=ultimo_resultado,
#         documentos_rag=docs_rag,
#         temperature=datos.temperature,
#         max_tokens=datos.max_tokens
#     )

#     # --- Extraer bancos mencionados en la respuesta ---
#     bancos_mencionados = set(re.findall(r"\bBBVA|ING|Santander\b", respuesta, re.IGNORECASE))

#     # --- Filtrar docs_rag para mostrar solo PDFs de los bancos mencionados ---
#     documentos_para_front = []
#     seen_files = set()
#     for d in docs_rag:
#         banco = (d.get("banco") or "").upper()
#         pdf = d.get("ruta_pdf")
#         if banco in bancos_mencionados and pdf:
#             filename = os.path.basename(pdf)
#             if filename not in seen_files:
#                 documentos_para_front.append({
#                     "origen": filename,
#                     "url": f"/pdfs/{filename}"
#                 })
#                 seen_files.add(filename)

#     return {
#         "ok": True,
#         "respuesta": respuesta,
#         "documentos_usados": documentos_para_front
#     }

@app.post("/preguntar")
def preguntar_llm(datos: PreguntaInput):
    logger.info(f"/preguntar recibida: '{datos.pregunta[:50]}...'")

    # --- Validación de entrada ---
    if not datos.pregunta.strip():
        logger.warning("Pregunta vacía recibida en /preguntar")
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")
    if not ultimo_resultado:
        logger.warning("Intento de /preguntar sin análisis previo")
        raise HTTPException(status_code=400, detail="No hay análisis previo. Envía el formulario primero.")

    resultado_actual = ultimo_resultado

    # --- Buscar documentos relevantes en Qdrant ---
    docs_rag = buscar_hipotecas_en_qdrant(
        query=datos.pregunta,
        top_k=5,
        min_score=0.15
    )

    # Normalizar ruta PDF si falta
    for d in docs_rag:
        if not d.get("ruta_pdf") and d.get("origen"):
            d["ruta_pdf"] = d["origen"].replace("\\", "/")

    # --- Generar respuesta con LLM ---
    respuesta = responder_pregunta_gemini(
        pregunta=datos.pregunta,
        contexto=resultado_actual,
        documentos_rag=docs_rag,
        temperature=datos.temperature,
        max_tokens=datos.max_tokens
    )

    # --- Detectar bancos mencionados en la respuesta ---
    BANCOS_KNOWN = ["BBVA", "ING", "SANTANDER"]  # se puede ampliar
    respuesta_upper = respuesta.upper()
    bancos_mencionados = set()
    for banco in BANCOS_KNOWN:
        if banco in respuesta_upper:
            bancos_mencionados.add(banco)
    logger.info(f"Bancos mencionados en la respuesta: {bancos_mencionados}")

    # --- Filtrar PDFs solo de bancos mencionados ---
    documentos_para_front = []
    seen_files = set()
    for d in docs_rag:
        banco_doc = (d.get("banco") or "").upper()
        pdf = d.get("ruta_pdf")
        if pdf and banco_doc in bancos_mencionados:
            filename = os.path.basename(pdf)
            if filename not in seen_files:
                documentos_para_front.append({
                    "origen": filename,
                    "url": f"/pdfs/{filename}"
                })
                seen_files.add(filename)

    logger.info(f"Se enviarán {len(documentos_para_front)} PDFs al frontend")

    return {
        "ok": True,
        "respuesta": respuesta,
        "documentos_usados": documentos_para_front
    }



# @app.post("/preguntar")
# def preguntar_llm(datos: PreguntaInput):
#     logger.info(f"/preguntar recibida: '{datos.pregunta[:50]}...'")
#     # para hacer preguntas sobre el análisis de hipoteca mediante LLM.
    
#     # Validación de entrada
#     if not datos.pregunta.strip():
#         logger.warning("Pregunta vacía recibida en /preguntar")
#         raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")
#     if not ultimo_resultado:
#         logger.warning("Intento de /preguntar sin análisis previo")
#         raise HTTPException(status_code=400, detail="No hay análisis previo. Envía el formulario primero.")

#     resultado_actual = ultimo_resultado

#     # RAG: buscar documentos relevantes
#     docs_rag = buscar_hipotecas_en_qdrant(
#         query=datos.pregunta,
#         top_k=5,
#         min_score=0.15
#     )


#     for d in docs_rag:
#         # Si no hay ruta_pdf pero sí hay origen, construye la ruta PDF
#         if not d.get("ruta_pdf") and d.get("origen"):
#             # Reemplaza barras invertidas por normales
#             d["ruta_pdf"] = d["origen"].replace("\\", "/")


#     # Llamada al LLM
#     respuesta = responder_pregunta_gemini(
#         pregunta=datos.pregunta,
#         contexto=resultado_actual,
#         documentos_rag=docs_rag,
#         temperature=datos.temperature,
#         max_tokens=datos.max_tokens
#     )

#     # Construir lista de documentos para el frontend
#     # Endpoint /preguntar corregido

#     # documentos_para_front = []
#     # for d in docs_rag:
#     #     # usa ruta_pdf si existe, sino origen
#     #     raw_path = d.get("ruta_pdf") or d.get("origen") or "desconocido"
#     #     ruta_pdf = raw_path.replace("\\", "/")  # reemplaza \ por /
#     #     filename = os.path.basename(ruta_pdf)
#     #     documentos_para_front.append({
#     #         "origen": filename,
#     #         "url": f"/pdfs/{filename}"  # URL limpia para el frontend
#     #     })

#     documentos_para_front = []
#     seen_files = set()

#     for d in docs_rag:
#         if d.get("ruta_pdf"):
#             filename = os.path.basename(d["ruta_pdf"])
#             if filename not in seen_files:
#                 documentos_para_front.append({
#                     "origen": filename,
#                     "url": f"/pdfs/{filename}" # URL para acceder al PDF
#                 })
#                 seen_files.add(filename)



#     return {
#         "ok": True,
#         "respuesta": respuesta,
#         "documentos_usados": documentos_para_front
#     }



# @app.get("/pdf/{filename}")
# def get_pdf(filename: str):
#     ruta = f"../data/docs_bancarios/{filename}"
#     if not os.path.exists(ruta):
#         raise HTTPException(status_code=404, detail="PDF no encontrado")
#     return FileResponse(ruta, media_type="application/pdf", filename=filename)
