# Imagen base
FROM python:3.12-slim

# Carpeta de trabajo
WORKDIR /app

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Exponer puerto del backend
EXPOSE 8000

# Ejecutar Uvicorn
CMD ["uvicorn", "hipotecassist_api:app", "--host", "0.0.0.0", "--port", "8000"]
