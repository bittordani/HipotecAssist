FROM python:3.12-slim

WORKDIR /app

# deps del sistema (útiles para sentence-transformers, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar PyTorch CPU explícitamente
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir torch==2.9.1+cpu --index-url https://download.pytorch.org/whl/cpu
    
# Instala sentence-transformers si no está en requirements
RUN pip install sentence-transformers
# Pre-descarga el modelo para que esté en la imagen
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el código del backend
COPY . .

# Creamos una variable para que el puerto sea dinamico para local como para CloudRun
# local=8000 y Pipeline para deployCloudRun=8080
ARG PORT=8000
ENV PORT $PORT
EXPOSE $PORT


CMD sh -c "uvicorn hipotecassist_api:app --host 0.0.0.0 --port $PORT"
