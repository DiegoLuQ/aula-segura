# /backend/Dockerfile
FROM python:3.11-slim

# Establecemos el directorio de trabajo en /app
WORKDIR /app

# Copiamos solo el código de tu proyecto
COPY . /app

# Instalamos las dependencias del proyecto
RUN pip install --no-cache-dir -r requirements.txt

# Exponemos el puerto de FastAPI
EXPOSE 8000

# Lanzamos la aplicación
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]