# /backend/Dockerfile
FROM my-python-fastapi:1.1

# Copiamos solo el código de tu proyecto
COPY . /app

# Exponemos el puerto de FastAPI
EXPOSE 8000

# Lanzamos la aplicación
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]