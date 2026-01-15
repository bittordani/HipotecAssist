FROM python:3.12-slim

WORKDIR /app

# deps del sistema (útiles para sentence-transformers, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar PyTorch CPU explícitamente
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir torch==2.9.1+cpu --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el código del backend
COPY . .

# COPY data /app/data

ARG PORT=8000
ENV PORT $PORT
EXPOSE $PORT

# CMD ["uvicorn", "hipotecassist_api:app", "--host", "0.0.0.0", "--port", "8000"]
# CMD ["uvicorn", "hipotecassist_api:app", "--host", "0.0.0.0", "--port", "${PORT}"]
# CMD ["sh", "-c", "uvicorn hipotecassist_api:app --host 0.0.0.0 --port $PORT"]
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "${PORT}"]

CMD sh -c "uvicorn hipotecassist_api:app --host 0.0.0.0 --port $PORT"