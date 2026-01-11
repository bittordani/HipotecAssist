# HipotecAssist

> **Asistente hipotecario inteligente con IA**: Análisis, simulaciones y asesoramiento personalizado basado en documentación bancaria oficial.

⚠️ Disclaimer / Aviso Legal del Asistente Financiero

Este asistente financiero tiene un propósito educativo e informativo. Las simulaciones, explicaciones y respuestas generadas se basan en datos proporcionados por el usuario y en modelos de lenguaje artificial, y no constituyen asesoramiento financiero, legal ni fiscal profesional.
Antes de tomar cualquier decisión económica relevante, se recomienda consultar con un asesor financiero o legal debidamente cualificado.
El equipo desarrollador no se hace responsable del uso que se haga de la información generada por el sistema.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](https://docs.docker.com/compose/)

**Equipo**: Víctor Daniel Martínez Martínez | Iván Ramos González | Guillermo Prieto García

---

## Descripción

**HipotecAssist** es una solución web impulsada por inteligencia artificial que democratiza el acceso a asesoramiento hipotecario profesional. Combina cálculos financieros avanzados con un asistente conversacional basado en RAG (Retrieval-Augmented Generation) para ofrecer:

- **Simulaciones hipotecarias detalladas** con métricas financieras (DTI, LTV)
- **Asistente IA conversacional** que responde preguntas contextualizadas
- **RAG sobre documentos bancarios reales** (FIPRE, FIPER, folletos comerciales)
- **Comparativas de subrogación** y análisis de ahorro
- **Stress tests** de subidas de tipos de interés
- **Disponibilidad 24/7** sin intermediarios

---

## Características Principales

### Simulador Hipotecario Avanzado

- Cálculo de cuota mensual (sistema de amortización francés)
- Tabla de amortización detallada (hitos: año 1, 5, 10 y final)
- Intereses totales restantes
- Simulación de amortización anticipada (1k, 5k, 10k €)
- Comparativa de ofertas de subrogación

### Métricas Financieras

- **DTI (Debt-to-Income)**: Ratio de endeudamiento
- **LTV (Loan-to-Value)**: Ratio préstamo-valor
- Avisos personalizados según riesgo financiero

### Asistente IA con RAG

- Motor: **Google Gemini 2.5 Flash Lite**
- Búsqueda semántica en documentos bancarios oficiales
- Respuestas contextualizadas al análisis del usuario
- Enlaces directos a PDFs de referencia

### Stress Tests

- Simulación de subidas de tipos de interés (+1%, +2%)
- Impacto en cuota mensual

---

## Modelos de Negocio

| Modelo | Descripción | Ventajas | Consideraciones |
|--------|-------------|----------|-----------------|
| **🏦 B2B - Bancos** | Integración en plataformas bancarias | Mercado grande, asesoramiento híbrido (IA + humano) | Requiere personalización por entidad |
| **🏢 B2B - Asesorías** | Herramienta SaaS para asesorías independientes | Complementa servicio profesional, eficiencia | Competencia con asesoramiento tradicional |
| **👤 B2C - Particulares** | Servicio directo (freemium/suscripción) | Objetividad total, sin conflictos de interés | Adquisición de usuarios, sin soporte humano |

---

## Quickstart

### Prerrequisitos

- [Docker](https://docs.docker.com/get-docker/) y [Docker Compose](https://docs.docker.com/compose/install/)
- Claves API:
  - [Google Gemini API Key](https://ai.google.dev/)
  - [Qdrant Cloud](https://cloud.qdrant.io/)

### Instalación

1. **Clonar el repositorio**

```bash
git clone https://github.com/bittordani/HipotecAssist.git
cd HipotecAssist
```

2. **Configurar variables de entorno**

Copia el archivo de ejemplo y edita con tus claves:

```bash
cp .env.example .env
nano .env  # o usa tu editor preferido
```

Contenido del `.env`:

```bash
# Google Gemini API
GOOGLE_API_KEY=tu_api_key_aqui

# Qdrant Cloud
QDRANT_URL=https://xxxxx.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=tu_qdrant_api_key_aqui
```

3. **Desplegar con Docker Compose**

```bash
docker-compose up -d --build
```

4. **Acceder a la aplicación**

- **Frontend**: [http://localhost:8080](http://localhost:8080)
- **API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## Ingesta de Documentos Bancarios

Para que el asistente IA tenga acceso a documentación bancaria, debes procesar los PDFs:

1. **Colocar PDFs en la carpeta de datos**

```bash
# Añade tus PDFs bancarios aquí
ls data/docs_bancarios/
# Ejemplo: BBVA_FIPRE.pdf, Santander_FIPER.pdf, etc.
```

2. **Ejecutar el script de ingesta**

```bash
docker-compose exec backend python scripts/ingest_docs.py
```

Este script:
- Lee todos los PDFs de `data/docs_bancarios/`
- Divide el texto en fragmentos (chunks) de ~500 caracteres
- Genera embeddings con `all-MiniLM-L6-v2`
- Sube los vectores a Qdrant Cloud

> **Nota**: El script borra y recrea la colección en cada ejecución para evitar duplicados.

---

## Arquitectura

Puedes consultar la arquitectura en el siguiente link:
https://drive.google.com/file/d/18l0uQ1Plih77QmoSHPO2RNTXFXLWBfhq/view?usp=sharing

### Stack Tecnológico

**Backend**:
- FastAPI (Python 3.11+)
- Google Gemini 2.5 Flash Lite
- Qdrant Cloud (base de datos vectorial)
- Sentence Transformers (embeddings)
- pypdf (procesamiento de PDFs)

**Frontend**:
- Nginx Alpine
- JavaScript vanilla (ES6+)
- CSS3

**Infraestructura**:
- Docker + Docker Compose
- GitHub Actions (CI/CD)

---

## Uso de la Aplicación

### 1 Realizar Análisis Hipotecario

1. Accede a [http://localhost:8080](http://localhost:8080)
2. Completa el formulario con los datos de tu hipoteca:
   - Capital pendiente
   - Años restantes
   - Tipo de interés (Fijo o Variable)
   - Datos opcionales: ingresos, valor vivienda, etc.
3. Haz clic en **"Analizar"**
4. Revisa los resultados:
   - Métricas (cuota, DTI, LTV)
   - Tabla de amortización
   - Stress tests
   - Avisos financieros

### 2 Consultar al Asistente IA

Una vez realizado el análisis, puedes hacer preguntas como:

- *"¿Puedo encontrar mejores condiciones en otro banco?"*
- *"¿Me conviene amortizar anticipadamente?"*
- *"¿Qué pasaría si suben los tipos de interés?"*
- *"¿Cuál es mi capacidad de endeudamiento?"*

El asistente responderá basándose en:
- Tu análisis actual
- Documentación bancaria oficial (PDFs)
- Mejores prácticas financieras

---

## Desarrollo

### Estructura del Proyecto

```
HipotecAssist/
├── backend/
│   ├── hipotecassist_api.py    # API principal
│   ├── llm.py                   # Integración Gemini
│   ├── routers/
│   │   └── search.py            # Endpoints RAG
│   ├── services/
│   │   └── qdrant_connection.py # Cliente Qdrant
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── web/
│   │   ├── index.html
│   │   ├── app.js
│   │   └── styles.css
│   ├── nginx.conf
│   └── Dockerfile
├── data/
│   └── docs_bancarios/          # PDFs bancarios
├── scripts/
│   └── ingest_docs.py           # Script de ingesta
├── tests/
│   └── test_smoke.py
├── docker-compose.yml
├── .env.example
└── README.md
```

### Comandos Útiles

```bash
# Ver logs en tiempo real
docker-compose logs -f backend

# Reiniciar solo el backend
docker-compose restart backend

# Parar todos los servicios
docker-compose down

# Ejecutar tests
docker-compose exec backend pytest tests/

# Acceder al shell del backend
docker-compose exec backend bash

# Reconstruir sin caché
docker-compose build --no-cache
```

### API Endpoints 

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/` | Health check básico |
| `GET` | `/health` | Health check con uptime |
| `POST` | `/analisis` | Análisis hipotecario completo |
| `POST` | `/preguntar` | Consulta al asistente IA |
| `GET` | `/buscar` | Búsqueda directa en Qdrant |
| `GET` | `/pdfs/{filename}` | Servir documento PDF |
| `GET` | `/docs` | Documentación Swagger |

---

## 🙏 Agradecimientos

Queremos expresar nuestro agradecimiento al director y tutor del máster por su orientación, disponibilidad y asesoramiento a lo largo del desarrollo de este proyecto. Su acompañamiento ha sido clave para guiarnos en la toma de decisiones técnicas y metodológicas y para mantener el enfoque del trabajo en todo momento.
Asimismo, extendemos nuestro reconocimiento a todo el equipo docente de los distintos módulos impartidos, cuyo esfuerzo formativo y compromiso académico han contribuido de manera decisiva a la adquisición de los conocimientos y competencias necesarios para la realización de este proyecto.
Finalmente, queremos agradecer también el apoyo y la comprensión de nuestras familias, que han sabido acompañarnos durante este proceso y a quienes, inevitablemente, hemos “robado” muchas horas de tiempo personal para poder llevarlo a término.

El equipo de trabajo:

- Iván
- Guillermo
- Víctor Daniel

<div align="center">

**[⬆ Volver arriba](#-hipotecassist)**

Hecho con ❤️ por el equipo HipotecAssist

</div>