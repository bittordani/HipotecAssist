FROM python:3.12-slim

WORKDIR /app

# deps del sistema (útiles para sentence-transformers, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiamos requirements desde la raíz del repo
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiamos el código del backend
COPY backend/ /app/

EXPOSE 8000

CMD ["uvicorn", "hipotecassist_api:app", "--host", "0.0.0.0", "--port", "8000"]
