# backend/hipotecassist_api.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from math import pow
from typing import Optional, List, Dict
import logging
import time
from datetime import datetime

from routers.search import router as search_router
from routers.search import buscar_hipotecas_en_qdrant
from llm import responder_pregunta_gemini

# -------------------- Estado global --------------------
ultimo_resultado: Optional[Dict] = None

# -------------------- Logging --------------------
logging.getLogger().handlers.clear()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# -------------------- App --------------------
app = FastAPI()
app.include_router(search_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- Utilidades de cálculo --------------------
def cuota_mensual(P: float, rate_annual: float, n_months: int) -> float:
    r = rate_annual / 12.0
    if r <= 0:
        return P / n_months
    return P * (r * pow(1 + r, n_months)) / (pow(1 + r, n_months) - 1)

def intereses_restantes_aprox(P: float, rate_annual: float, n_months: int) -> float:
    c = cuota_mensual(P, rate_annual, n_months)
    total = c * n_months
    return max(0.0, total - P)

def resumen_amortizacion(P: float, rate_annual: float, n_months: int, hitos=(12, 60, 120)) -> List[Dict]:
    r = rate_annual / 12.0
    c = cuota_mensual(P, rate_annual, n_months)
    bal = P
    interes_acum = 0.0
    out = []
    setpoints = set(hitos) | {n_months}

    for m in range(1, n_months + 1):
        i = bal * r
        p = c - i
        bal = max(0.0, bal - p)
        interes_acum += i

        if m in setpoints:
            out.append({
                "mes": m,
                "cuota": round(c, 2),
                "interes_mes": round(i, 2),
                "amortizado_mes": round(p, 2),
                "saldo": round(bal, 2),
                "interes_acum": round(interes_acum, 2),
            })
        if bal <= 0:
            break

    return out

def ahorro_amortizacion_extra(P: float, rate_annual: float, n_months: int, extra: float, when_month: int = 1) -> float:
    r = rate_annual / 12.0
    c = cuota_mensual(P, rate_annual, n_months)

    b = P
    total_i_no = 0.0
    for _ in range(1, n_months + 1):
        i = b * r
        total_i_no += i
        b = max(0.0, b - (c - i))
        if b <= 0:
            break

    b = P
    total_i_si = 0.0
    for m in range(1, n_months + 1):
        i = b * r
        if m == when_month:
            b = max(0.0, b - extra)

        pay = c if b + i > c else (b + i)
        total_i_si += min(i, pay)
        b = max(0.0, b - (pay - i))
        if b <= 0:
            break

    return round(max(0.0, total_i_no - total_i_si), 2)

def stress_test_cuota(P: float, rate_annual: float, n_months: int, deltas=(0.01, 0.02)):
    base = cuota_mensual(P, rate_annual, n_months)
    res = []
    for d in deltas:
        r2 = max(0.0, rate_annual + d)
        c2 = cuota_mensual(P, r2, n_months)
        res.append({
            "delta_tipo_pp": int(d * 100),
            "tipo_resultante": round((r2 * 100), 3),
            "cuota": round(c2, 2),
            "diferencia": round(c2 - base, 2),
        })
    return round(base, 2), res

def calcula_dti(cuota: float, ingresos_mensuales: Optional[float]) -> Optional[float]:
    if not ingresos_mensuales or ingresos_mensuales <= 0:
        return None
    return round((cuota / ingresos_mensuales) * 100.0, 2)

def calcula_ltv(capital_pendiente: float, valor_vivienda: Optional[float]) -> Optional[float]:
    if not valor_vivienda or valor_vivienda <= 0:
        return None
    return round((capital_pendiente / valor_vivienda) * 100.0, 2)

# -------------------- Modelos --------------------
class AnalisisInput(BaseModel):
    capital_pendiente: float = Field(..., gt=0)
    anos_restantes: int = Field(..., gt=0)
    tipo: str = Field("fijo", description="fijo | variable")
    tin: Optional[float] = None
    euribor: Optional[float] = None
    diferencial: Optional[float] = None
    cuota_actual: Optional[float] = None
    ingresos_mensuales: Optional[float] = None
    otras_deudas_mensuales: Optional[float] = 0.0
    valor_vivienda: Optional[float] = None
    oferta_alternativa_tin: Optional[float] = None

class PreguntaInput(BaseModel):
    pregunta: str
    temperature: float = 0.2
    max_tokens: int = 250

# -------------------- Middleware logging --------------------
@app.middleware("http")
async def simple_logger(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration:.2f}s)")
    return response

# -------------------- Básicos --------------------
@app.get("/")
def root():
    logger.info("API activa CORRECTAMENTE")
    return {"ok": True, "msg": "API de análisis hipotecario activa"}

start_time = datetime.utcnow()

@app.get("/health")
def health_check():
    uptime = datetime.utcnow() - start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_formatted = f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
    return {"status": "ok", "uptime": uptime_formatted}

# -------------------- /analisis --------------------
@app.post("/analisis")
def analisis(data: AnalisisInput):
    global ultimo_resultado

    logger.info(f"Analizando hipoteca: tipo={data.tipo}, capital={data.capital_pendiente}, años={data.anos_restantes}")

    P = data.capital_pendiente
    n_meses = data.anos_restantes * 12

    if data.tipo.lower() == "variable":
        if data.euribor is None or data.diferencial is None:
            logger.warning("Faltan euribor o diferencial para hipoteca variable")
            return {"ok": False, "error": "Para 'variable' necesitas euribor y diferencial."}
        tipo_anual = (data.euribor + data.diferencial) / 100.0
        tipo_label = f"variable (Euríbor {data.euribor:.2f}% + {data.diferencial:.2f}%)"
    else:
        if data.tin is None:
            logger.warning("Falta TIN para hipoteca fija")
            return {"ok": False, "error": "Para 'fijo' necesitas el TIN (%)."}
        tipo_anual = data.tin / 100.0
        tipo_label = f"fijo ({data.tin:.2f}%)"

    cuota_estimada = cuota_mensual(P, tipo_anual, n_meses)
    cuota_efectiva = data.cuota_actual or cuota_estimada

    intereses_totales = intereses_restantes_aprox(P, tipo_anual, n_meses)
    resumen = resumen_amortizacion(P, tipo_anual, n_meses, hitos=(12, 60, 120))

    dti = calcula_dti(cuota_efectiva + (data.otras_deudas_mensuales or 0.0), data.ingresos_mensuales)
    ltv = calcula_ltv(P, data.valor_vivienda)

    cuota_base, stress = stress_test_cuota(P, tipo_anual, n_meses, deltas=(0.01, 0.02))

    ahorro_1k = ahorro_amortizacion_extra(P, tipo_anual, n_meses, 1000.0, 1)
    ahorro_5k = ahorro_amortizacion_extra(P, tipo_anual, n_meses, 5000.0, 1)
    ahorro_10k = ahorro_amortizacion_extra(P, tipo_anual, n_meses, 10000.0, 1)

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

# -------------------- Helpers --------------------
def detectar_banco_desde_texto(texto: str) -> Optional[str]:
    t = (texto or "").lower()
    if "ing" in t:
        return "ING"
    if "santander" in t:
        return "Santander"
    if "bbva" in t:
        return "BBVA"
    return None

# -------------------- /preguntar --------------------
@app.post("/preguntar")
def preguntar(body: PreguntaInput):
    global ultimo_resultado

    if not ultimo_resultado:
        logger.warning("Intento de /preguntar sin análisis previo")
        return {"ok": False, "error": "No hay análisis previo. Envía el formulario primero."}

    banco = detectar_banco_desde_texto(body.pregunta)

    # RAG directo (sin requests a localhost, evita líos en Docker)
    docs_rag = buscar_hipotecas_en_qdrant(
        query=body.pregunta,
        top_k=5,
        banco=banco,
        min_score=0.15,
    )
    logger.info(f"/preguntar: RAG docs={len(docs_rag)} banco_filtro={banco}")

    respuesta = responder_pregunta_gemini(
        pregunta=body.pregunta,
        contexto=ultimo_resultado,
        documentos_rag=docs_rag,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )

    return {"ok": True, "respuesta": respuesta, "documentos_usados": docs_rag}
