FROM python:3.12-slim

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalamos dependencias
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiamos SOLO el backend dentro de /app
COPY backend/ /app/

# Aseguramos que Python vea /app como raíz de imports
ENV PYTHONPATH=/app

# Arrancamos FastAPI (tu archivo principal es hipotecassist_api.py)
CMD ["uvicorn", "hipotecassist_api:app", "--host", "0.0.0.0", "--port", "8000"]
