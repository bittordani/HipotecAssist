from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from math import pow
from typing import Optional, List, Dict
import requests
import os

from fastapi.staticfiles import StaticFiles
from pathlib import Path

ultimo_resultado = None

app = FastAPI()

# # Carpeta frontend relativa a la raíz del proyecto
# frontend_path = Path(__file__).parent.parent / "frontend" / "web"
# app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

# CORS para desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en prod: pon tu dominio
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Utilidades de cálculo ----------
def cuota_mensual(P: float, rate_annual: float, n_months: int) -> float:
    r = rate_annual / 12.0
    if r <= 0:
        return P / n_months
    return P * (r * pow(1 + r, n_months)) / (pow(1 + r, n_months) - 1)

def intereses_restantes_aprox(P: float, rate_annual: float, n_months: int) -> float:
    """Aproximación del total de intereses restantes suponiendo tipo constante."""
    c = cuota_mensual(P, rate_annual, n_months)
    total = c * n_months
    return max(0.0, total - P)

def resumen_amortizacion(P: float, rate_annual: float, n_months: int, hitos=(12,60,120)) -> List[Dict]:
    """Devuelve saldo/intereses en meses clave (1y,5y,10y y final)."""
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

def ahorro_amortizacion_extra(P: float, rate_annual: float, n_months: int, extra: float, when_month: int=1) -> float:
    """Ahorro total de intereses por amortizar 'extra' en el mes indicado."""
    r = rate_annual / 12.0
    c = cuota_mensual(P, rate_annual, n_months)

    # sin extra
    b = P
    total_i_no = 0.0
    for _ in range(1, n_months + 1):
        i = b * r
        total_i_no += i
        b = max(0.0, b - (c - i))
        if b <= 0:
            break

    # con extra
    b = P
    total_i_si = 0.0
    for m in range(1, n_months + 1):
        i = b * r
        if m == when_month:
            b = max(0.0, b - extra)
        pay = c if b + i > c else (b + i)  # última cuota
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
            "delta_tipo_pp": int(d*100),
            "tipo_resultante": round((r2*100), 3),
            "cuota": round(c2, 2),
            "diferencia": round(c2 - base, 2),
        })
    return round(base, 2), res

def calcula_dti(cuota_mensual: float, ingresos_mensuales: Optional[float]) -> Optional[float]:
    if not ingresos_mensuales or ingresos_mensuales <= 0:
        return None
    return round((cuota_mensual / ingresos_mensuales) * 100.0, 2)

def calcula_ltv(capital_pendiente: float, valor_vivienda: Optional[float]) -> Optional[float]:
    if not valor_vivienda or valor_vivienda <= 0:
        return None
    return round((capital_pendiente / valor_vivienda) * 100.0, 2)

# ---------- Esquema de entrada ----------
class AnalisisInput(BaseModel):
    # Datos que suelen tener los usuarios:
    capital_pendiente: float = Field(..., gt=0, description="Capital que queda por pagar (€)")
    anos_restantes: int = Field(..., gt=0, description="Años que quedan (enteros)")
    tipo: str = Field("fijo", description="fijo | variable")
    tin: Optional[float] = Field(None, description="TIN actual en % (si es fijo)")
    euribor: Optional[float] = Field(None, description="Euríbor actual en % (si es variable)")
    diferencial: Optional[float] = Field(None, description="Spread en % (si es variable)")
    cuota_actual: Optional[float] = Field(None, description="Si la sabes, mejor para DTI")
    ingresos_mensuales: Optional[float] = Field(None, description="Ingresos netos mensuales del hogar")
    otras_deudas_mensuales: Optional[float] = Field(0.0, description="Cuotas de otras deudas/mes")
    valor_vivienda: Optional[float] = Field(None, description="Valor aproximado actual")
    oferta_alternativa_tin: Optional[float] = Field(None, description="Tipo alternativo para comparar (TAE/TIN %)")


class PreguntaInput(BaseModel):
    pregunta: str


# ---------- Endpoints ----------
@app.get("/")
def root():
    return {"ok": True, "msg": "API de análisis hipotecario activa"}

@app.post("/analisis")
def analisis(data: AnalisisInput):
    print("Datos recibidos:", data)
    P = data.capital_pendiente
    n_meses = data.anos_restantes * 12

    # tipo efectivo anual
    if data.tipo.lower() == "variable":
        if data.euribor is None or data.diferencial is None:
            return {"ok": False, "error": "Para 'variable' necesitas euribor y diferencial."}
        tipo_anual = (data.euribor + data.diferencial) / 100.0
        tipo_label = f"variable (Euríbor {data.euribor:.2f}% + {data.diferencial:.2f}%)"
    else:
        if data.tin is None:
            return {"ok": False, "error": "Para 'fijo' necesitas el TIN (%)."}
        tipo_anual = data.tin / 100.0
        tipo_label = f"fijo ({data.tin:.2f}%)"

    # cuota estimada si no la dan
    cuota_estimada = cuota_mensual(P, tipo_anual, n_meses)
    cuota_efectiva = data.cuota_actual or cuota_estimada

    # métricas base
    intereses_totales = intereses_restantes_aprox(P, tipo_anual, n_meses)
    resumen = resumen_amortizacion(P, tipo_anual, n_meses, hitos=(12,60,120))

    # DTI & LTV
    dti = calcula_dti(cuota_efectiva + (data.otras_deudas_mensuales or 0.0), data.ingresos_mensuales)
    ltv = calcula_ltv(P, data.valor_vivienda)

    # Stress test de cuota
    cuota_base, stress = stress_test_cuota(P, tipo_anual, n_meses, deltas=(0.01, 0.02))

    # Amortización extra típica
    ahorro_1k = ahorro_amortizacion_extra(P, tipo_anual, n_meses, 1000.0, 1)
    ahorro_5k = ahorro_amortizacion_extra(P, tipo_anual, n_meses, 5000.0, 1)
    ahorro_10k = ahorro_amortizacion_extra(P, tipo_anual, n_meses, 10000.0, 1)

    # Comparativa rápida de subrogación (si dan oferta alternativa)
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

    # Semáforos y avisos básicos
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
    "entrada": {
        "capital_pendiente": P,
        "anos_restantes": data.anos_restantes,
        "tipo": tipo_label
    },  
        "metricas": {
            "cuota_efectiva": round(cuota_efectiva, 2),
            "cuota_estimada": round(cuota_estimada, 2),
            "intereses_restantes_aprox": round(intereses_totales, 2),
            "dti": dti,
            "ltv": ltv
        },
        "stress_test": {
            "cuota_base": cuota_base,
            "escenarios": stress
        },
        "amortizacion_extra": {
            "ahorro_1k": ahorro_1k,
            "ahorro_5k": ahorro_5k,
            "ahorro_10k": ahorro_10k
        },
        "resumen_amortizacion": resumen,
        "comparativa_subrogacion": comparativa,
        "avisos": avisos
    }

    global ultimo_resultado
    ultimo_resultado = resultado

    return resultado



@app.post("/preguntar")
def preguntar(data: PreguntaInput):
    global ultimo_resultado

    if not ultimo_resultado:
        return {"ok": False, "error": "No hay análisis previo. Envía el formulario primero."}

    api_key = os.getenv("GROQ_API_KEY")  # tu clave
    url = "https://api.groq.com/openai/v1/chat/completions"

    # Construimos el mensaje con contexto
    messages = [
        {"role": "system", "content": "Eres un asistente hipotecario. Y das respuestas muy cortas para que el usuario entienda rapido"},
        {"role": "system", "content": f"Contexto del usuario: {ultimo_resultado}"},
        {"role": "user", "content": data.pregunta}
    ]

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": messages
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        respuesta = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"ok": True, "respuesta": respuesta}
    except requests.HTTPError as e:
        return {"ok": False, "error": f"Error en la API: {e} - {resp.text}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
