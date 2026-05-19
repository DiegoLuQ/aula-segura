---
name: gestion_pdf_aula_segura
description: Habilidad para gestionar la subida, compresión con pikepdf y previsualización de documentos PDF en el sistema Aula Segura.
---

# Gestión de Documentos PDF

Esta habilidad proporciona las capacidades necesarias para manejar expedientes digitales en formato PDF, asegurando que los archivos estén optimizados para la web y sean fácilmente accesibles para su revisión sin necesidad de descarga previa.

## Capacidades

1.  **Subida Segura**: Manejo de archivos PDF vinculados a registros de estudiantes.
2.  **Optimización Automática**: Uso de `pikepdf` para comprimir flujos de datos y linealizar archivos.
3.  **Nomenclatura Estandarizada**: Generación automática de nombres según el formato `[TIPO]_[COLEGIO]_[FECHA]_[ID]_[RANDOM].pdf`.
4.  **Previsualización Inline**: Visualización de documentos en modales integrados sin forzar la descarga.
5.  **Gestión de Espacio**: Eliminación física de archivos al borrar registros de la base de datos.

## Instrucciones de Implementación

### Backend (FastAPI + pikepdf)

Para implementar esta habilidad en el backend, se deben seguir estos pasos:

1.  **Instalación**: Asegurarse de tener `pikepdf` instalado en el entorno.
2.  **Modelo**: La tabla debe contener campos para `tipo`, `nombre_archivo`, `ruta_archivo` y `tamanio`.
3.  **Lógica de Compresión**:
    ```python
    import pikepdf
    def compress_pdf(input_path, output_path):
        with pikepdf.open(input_path) as pdf:
            pdf.save(output_path, compress_streams=True, linearize=True)
    ```
4.  **Endpoints**:
    *   `POST /upload`: Recibe el archivo, lo guarda temporalmente, lo comprime y registra los metadatos (incluyendo el tamaño calculado).
    *   `GET /view`: Devuelve el archivo con `media_type="application/pdf"` para permitir la visualización inline.
    *   `DELETE`: Elimina tanto el registro como el archivo físico usando `os.remove()`.

### Frontend (HTML + Tailwind + JS)

1.  **Visor Modal**: Implementar un `<iframe>` dentro de un modal con `backdrop-blur` para la previsualización.
2.  **Gestión de Token**: Pasar el token de sesión como parámetro de consulta (`?token=...`) para autenticar la visualización inline en el `iframe`.
3.  **Tarjetas de Documento**: Usar un diseño basado en tarjetas que muestre el tipo de documento, el peso del archivo y proporcione acciones claras (Ver, Descargar, Eliminar).

## Reglas y Restricciones
- Solo se deben permitir archivos con extensión `.pdf`.
- La compresión debe ser obligatoria para todos los archivos subidos.
- Las descargas deben mantener el nombre original formateado por el sistema.
- El borrado de documentos es irreversible tanto en base de datos como en disco.
- Se debe validar que el usuario tenga permisos sobre el colegio del estudiante antes de permitir la subida o descarga.
