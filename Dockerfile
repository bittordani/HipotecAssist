# Imagen base de Python
FROM python:3.12-slim

# Crear carpeta de trabajo
WORKDIR /app

# Copiar requirements e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el backend y front
COPY backend ./backend
COPY frontend ./frontend

# Exponer el puerto
EXPOSE 8000

# Comando para ejecutar el backend
CMD ["uvicorn", "backend.hipoassist_api:app", "--host", "0.0.0.0", "--port", "8000"]
