#!/bin/bash
# Corregir permisos de la carpeta de trabajo para Apache/Python
chown -R www-data:www-data /var/www/html

# Ejecutar el comando principal del contenedor (Apache / Uvicorn)
exec "$@"
