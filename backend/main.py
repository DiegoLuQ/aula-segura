from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd
import io
import os
import shutil
import uuid
import pikepdf
from datetime import datetime
import models, schemas, auth, database, notifications

app = FastAPI(title="Sistema Aula Segura API")

@app.on_event("startup")
def _startup():
    # Inicia el hilo que envía los recordatorios programados
    notifications.iniciar_scheduler()

@app.get("/estudiantes/template")
def get_template(db: Session = Depends(database.get_db)):
    cols = [
        "ID COLEGIO", "RUT", "NOMBRE ESTUDIANTE", "CURSO", "CAUSA", 
        "FECHA INICIO PROCESO AULA SEGURA", "DESCARGOS", 
        "FECHA NOTIFICACIÓN MEDIDA", "FECHA RECEPCIÓN CARTA APELACIÓN", 
        "FECHA CONSEJO PROFESORES", "FECHA NOTIFICACIÓN FINAL \"MEDIDA\"", 
        "FECHA ENVÍO DE ANTECEDENTES SIE", "RESULTADO REVISIÓN EXPEDIENTE", "MEDIDA"
    ]
    df = pd.DataFrame(columns=cols)
    df.loc[0] = [
        1, "12.345.678-9", "JUAN PEREZ", "8° BÁSICO A", "AGRESIÓN FÍSICA", 
        "2024-03-01", "Alumno reconoce los hechos...", 
        "2024-03-05", "2024-03-10", 
        "2024-03-12", "2024-03-15", 
        "2024-03-20", "CIERRE DE EXPEDIENTE", "EXPULSIÓN"
    ]
    
    colegios = db.query(models.Colegio).all()
    df_colegios = pd.DataFrame([{"ID": c.id, "NOMBRE": c.nombre} for c in colegios])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
        df_colegios.to_excel(writer, index=False, sheet_name='Lista_Colegios')
    
    output.seek(0)
    headers = { 'Content-Disposition': 'attachment; filename="plantilla_aula_segura.xlsx"' }
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        io.BytesIO(output.getvalue()), 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear tablas al iniciar (si no existen)
models.Base.metadata.create_all(bind=database.engine)

# Migraciones ligeras: agregar columnas nuevas a tablas existentes (ignora si ya existen)
def _ensure_columns():
    from sqlalchemy import text
    stmts = [
        "ALTER TABLE pro_aula_segura_notificaciones ADD COLUMN hora_envio VARCHAR(5) NULL",
        "ALTER TABLE pro_aula_segura_notificaciones ADD COLUMN asunto_personalizado VARCHAR(255) NULL",
        "ALTER TABLE pro_aula_segura_envios_programados ADD COLUMN asunto VARCHAR(255) NULL",
        "ALTER TABLE pro_aula_segura_estudiantes ADD COLUMN consejo_confirmado BOOLEAN NULL",
    ]
    for s in stmts:
        try:
            with database.engine.begin() as conn:
                conn.execute(text(s))
        except Exception:
            pass  # la columna ya existe u otra causa no crítica

_ensure_columns()

@app.post("/login", response_model=schemas.Token)
def login(request: schemas.LoginRequest, db: Session = Depends(database.get_db)):
    user = db.query(models.Usuario).filter(models.Usuario.nombre == request.nombre).first()
    if not user or not auth.verify_password(request.clave, user.clave):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    rol = db.query(models.Rol).filter(models.Rol.id == user.id_rol).first()
    rol_name = rol.rol if rol else "viewer"
    
    access_token = auth.create_access_token(
        data={"sub": user.nombre, "role": rol_name, "id_colegio": user.id_colegio}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me", response_model=schemas.UsuarioResponse)
def get_me(current_user: dict = Depends(auth.get_current_user)):
    return current_user

@app.get("/estudiantes", response_model=List[schemas.Estudiante])
def get_estudiantes(
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    query = db.query(models.Estudiante).filter(models.Estudiante.estado == True)
    
    # Si es viewer, solo ve los de su colegio
    if current_user["rol"] == "viewer":
        query = query.filter(models.Estudiante.id_colegio == current_user["id_colegio"])
    
    # Si es super_viewer, ve todos (no entra en el filtro anterior)
    
    return query.all()

@app.get("/estudiantes/{id}", response_model=schemas.Estudiante)
def get_estudiante(
    id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    query = db.query(models.Estudiante).filter(models.Estudiante.id == id, models.Estudiante.estado == True)
    
    if current_user["rol"] == "viewer":
        query = query.filter(models.Estudiante.id_colegio == current_user["id_colegio"])
    
    db_estudiante = query.first()
    if not db_estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    
    return db_estudiante

@app.post("/estudiantes", response_model=schemas.Estudiante)
def create_estudiante(
    estudiante: schemas.EstudianteCreate,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    if current_user["rol"] not in ["lawyer", "admin"]:
        raise HTTPException(status_code=403, detail="No tiene permisos para agregar estudiantes")
    
    db_estudiante = models.Estudiante(
        **estudiante.dict(),
        id_usuario=current_user["id"]
    )
    db.add(db_estudiante)
    db.commit()
    db.refresh(db_estudiante)
    return db_estudiante

@app.put("/estudiantes/{id}", response_model=schemas.Estudiante)
def update_estudiante(
    id: int,
    estudiante: schemas.EstudianteCreate,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    if current_user["rol"] not in ["lawyer", "admin"]:
        raise HTTPException(status_code=403, detail="No tiene permisos para editar estudiantes")
    
    db_estudiante = db.query(models.Estudiante).filter(models.Estudiante.id == id).first()
    if not db_estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    
    for key, value in estudiante.dict().items():
        setattr(db_estudiante, key, value)
    
    db.commit()
    db.refresh(db_estudiante)
    return db_estudiante

@app.delete("/estudiantes/{id}")
def delete_estudiante(
    id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    if current_user["rol"] != "lawyer":
        raise HTTPException(status_code=403, detail="Solo el rol abogado puede eliminar registros")
    
    db_estudiante = db.query(models.Estudiante).filter(models.Estudiante.id == id).first()
    if not db_estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    
    db_estudiante.estado = False
    db.commit()
    return {"message": "Estudiante eliminado exitosamente"}

# --- GESTIÓN DE DOCUMENTOS ---

def compress_pdf(input_path, output_path):
    try:
        with pikepdf.open(input_path) as pdf:
            pdf.save(output_path, compress_streams=True, linearize=True)
        return True
    except Exception as e:
        print(f"Error comprimiendo PDF: {e}")
        return False

def get_file_size(file_path):
    try:
        size_bytes = os.path.getsize(file_path)
        if size_bytes < 1024: return f"{size_bytes} B"
        if size_bytes < 1024 * 1024: return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    except:
        return "Desconocido"

@app.post("/estudiantes/{id}/upload")
async def upload_documento(
    id: int,
    tipo: str,
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF")

    # Obtener datos para el nombre
    estudiante = db.query(models.Estudiante).filter(models.Estudiante.id == id).first()
    if not estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    
    colegio = db.query(models.Colegio).filter(models.Colegio.id == estudiante.id_colegio).first()
    nombre_colegio = colegio.nombre.replace(" ", "_") if colegio else "S_C"
    fecha_str = datetime.now().strftime("%Y-%m-%d")
    random_code = uuid.uuid4().hex[:6]
    
    # Nombre según regla: TIPO_COLEGIO_FECHA_ID_RANDOM.pdf
    filename = f"{tipo.replace(' ', '_')}_{nombre_colegio}_{fecha_str}_{id}_{random_code}.pdf"
    temp_path = os.path.join(UPLOAD_DIR, f"temp_{filename}")
    final_path = os.path.join(UPLOAD_DIR, filename)

    # Guardar temporal
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Comprimir
    if not compress_pdf(temp_path, final_path):
        # Si falla compresión, usamos el original
        shutil.copy(temp_path, final_path)
    
    # Borrar temporal
    if os.path.exists(temp_path):
        os.remove(temp_path)

    # Registrar en DB
    db_doc = models.Documento(
        estudiante_id=id,
        tipo=tipo,
        nombre_archivo=filename,
        ruta_archivo=final_path,
        tamanio=get_file_size(final_path)
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    return {"message": "Archivo subido y comprimido con éxito", "filename": filename}

@app.get("/estudiantes/{id}/documentos")
def get_documentos(
    id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    return db.query(models.Documento).filter(models.Documento.estudiante_id == id).all()

@app.get("/documentos/{doc_id}/download")
def download_documento(
    doc_id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    doc = db.query(models.Documento).filter(models.Documento.id == doc_id).first()
    if not doc or not os.path.exists(doc.ruta_archivo):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    return FileResponse(doc.ruta_archivo, filename=doc.nombre_archivo)

@app.get("/documentos/{doc_id}/view")
def view_documento(
    doc_id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    doc = db.query(models.Documento).filter(models.Documento.id == doc_id).first()
    if not doc or not os.path.exists(doc.ruta_archivo):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    return FileResponse(doc.ruta_archivo, media_type="application/pdf")

@app.delete("/documentos/{doc_id}")
def delete_documento(
    doc_id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    doc = db.query(models.Documento).filter(models.Documento.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Eliminar archivo físico
    if os.path.exists(doc.ruta_archivo):
        try:
            os.remove(doc.ruta_archivo)
        except Exception as e:
            print(f"Error eliminando archivo: {e}")

    # Eliminar de DB
    db.delete(doc)
    db.commit()
    
    return {"message": "Documento eliminado correctamente"}

# --- OTRAS MEDIDAS ---

@app.get("/otras-medidas/template")
def get_template_om(db: Session = Depends(database.get_db)):
    cols = ["ID COLEGIO", "RUT", "NOMBRE ESTUDIANTE", "CURSO", "FECHA INICIO", "CAUSA", "MEDIDA"]
    df = pd.DataFrame(columns=cols)
    df.loc[0] = [1, "12.345.678-9", "JUAN PEREZ", "1° MEDIO", "2024-05-01", "Faltas reiteradas", "SUSPENSIÓN 5 DÍAS"]
    
    colegios = db.query(models.Colegio).all()
    df_colegios = pd.DataFrame([{"ID": c.id, "NOMBRE": c.nombre} for c in colegios])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
        df_colegios.to_excel(writer, index=False, sheet_name='Lista_Colegios')
    
    output.seek(0)
    headers = { 'Content-Disposition': 'attachment; filename="plantilla_otras_medidas.xlsx"' }
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        io.BytesIO(output.getvalue()), 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

@app.get("/otras-medidas", response_model=List[schemas.OtraMedida])
def get_otras_medidas(
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    query = db.query(models.OtraMedida).filter(models.OtraMedida.estado == True)
    if current_user["rol"] == "viewer":
        query = query.filter(models.OtraMedida.id_colegio == current_user["id_colegio"])
    return query.all()

@app.get("/otras-medidas/{id}", response_model=schemas.OtraMedida)
def get_otra_medida(
    id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    query = db.query(models.OtraMedida).filter(models.OtraMedida.id == id, models.OtraMedida.estado == True)
    if current_user["rol"] == "viewer":
        query = query.filter(models.OtraMedida.id_colegio == current_user["id_colegio"])
    db_item = query.first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return db_item

@app.post("/otras-medidas", response_model=schemas.OtraMedida)
def create_otra_medida(
    item: schemas.OtraMedidaCreate,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    if current_user["rol"] not in ["lawyer", "admin"]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    db_item = models.OtraMedida(**item.dict(), id_usuario=current_user["id"])
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@app.put("/otras-medidas/{id}", response_model=schemas.OtraMedida)
def update_otra_medida(
    id: int,
    item: schemas.OtraMedidaCreate,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    if current_user["rol"] not in ["lawyer", "admin"]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    db_item = db.query(models.OtraMedida).filter(models.OtraMedida.id == id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    for key, value in item.dict().items():
        setattr(db_item, key, value)
    db.commit()
    db.refresh(db_item)
    return db_item

@app.delete("/otras-medidas/{id}")
def delete_otra_medida(
    id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    if current_user["rol"] != "lawyer":
        raise HTTPException(status_code=403, detail="Solo abogados pueden eliminar")
    db_item = db.query(models.OtraMedida).filter(models.OtraMedida.id == id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    db_item.estado = False
    db.commit()
    return {"message": "Eliminado exitosamente"}

@app.post("/otras-medidas/{id}/upload")
async def upload_documento_otra_medida(
    id: int,
    tipo: str,
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Solo PDFs")
    
    item = db.query(models.OtraMedida).filter(models.OtraMedida.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    
    colegio = db.query(models.Colegio).filter(models.Colegio.id == item.id_colegio).first()
    nombre_colegio = colegio.nombre.replace(" ", "_") if colegio else "S_C"
    filename = f"OM_{tipo.replace(' ', '_')}_{nombre_colegio}_{datetime.now().strftime('%Y-%m-%d')}_{id}_{uuid.uuid4().hex[:6]}.pdf"
    path = os.path.join(UPLOAD_DIR, filename)

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    db_doc = models.DocumentoOtraMedida(
        otra_medida_id=id,
        tipo=tipo,
        nombre_archivo=filename,
        ruta_archivo=path,
        tamanio=get_file_size(path)
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    return {"message": "Subido con éxito", "filename": filename}

@app.get("/otras-medidas/{id}/documentos")
def get_documentos_otra_medida(id: int, db: Session = Depends(database.get_db)):
    return db.query(models.DocumentoOtraMedida).filter(models.DocumentoOtraMedida.otra_medida_id == id).all()

@app.get("/documentos-om/{doc_id}/view")
def view_documento_om(doc_id: int, db: Session = Depends(database.get_db)):
    doc = db.query(models.DocumentoOtraMedida).filter(models.DocumentoOtraMedida.id == doc_id).first()
    if not doc or not os.path.exists(doc.ruta_archivo):
        raise HTTPException(status_code=404, detail="No encontrado")
    return FileResponse(doc.ruta_archivo, media_type="application/pdf")

@app.delete("/documentos-om/{doc_id}")
def delete_documento_om(doc_id: int, db: Session = Depends(database.get_db)):
    doc = db.query(models.DocumentoOtraMedida).filter(models.DocumentoOtraMedida.id == doc_id).first()
    if not doc: raise HTTPException(status_code=404, detail="No encontrado")
    if os.path.exists(doc.ruta_archivo): os.remove(doc.ruta_archivo)
    db.delete(doc)
    db.commit()
    return {"message": "Eliminado"}

@app.post("/otras-medidas/upload")
async def upload_otras_medidas(
    file: UploadFile = File(...),
    id_colegio: int = Form(...),
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    if current_user["rol"] not in ["lawyer", "admin"]:
        raise HTTPException(status_code=403, detail="Sin permisos")
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        registros = 0
        for _, row in df.iterrows():
            def get_val(col, default=None):
                val = row.get(col)
                return default if pd.isna(val) else val
            def get_str_val(col, default=""):
                val = row.get(col)
                if pd.isna(val): return default
                if isinstance(val, (datetime, pd.Timestamp)):
                    return val.strftime("%Y-%m-%d")
                val_str = str(val).strip()
                if val_str.endswith(" 00:00:00"):
                    return val_str.replace(" 00:00:00", "")
                return val_str
            def parse_date(col):
                val = row.get(col)
                if pd.isna(val): return None
                try: return pd.to_datetime(val).date()
                except: return None

            db_item = models.OtraMedida(
                rut=get_str_val("RUT"),
                nombre_estudiante=get_str_val("NOMBRE ESTUDIANTE"),
                curso=get_str_val("CURSO"),
                fecha_inicio=parse_date("FECHA INICIO") or parse_date("FECHA INICIO PROCESO AULA SEGURA"),
                causa=get_str_val("CAUSA"),
                medida=get_str_val("MEDIDA"),
                id_colegio=int(get_val("ID COLEGIO", id_colegio)),
                id_usuario=current_user["id"]
            )
            db.add(db_item)
            registros += 1
        db.commit()
        return {"count": registros, "message": "Carga exitosa"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/colegios")
def get_colegios(db: Session = Depends(database.get_db)):
    return db.query(models.Colegio).all()

@app.get("/roles")
def get_roles(db: Session = Depends(database.get_db)):
    return db.query(models.Rol).all()

@app.post("/estudiantes/upload")
async def upload_estudiantes(
    file: UploadFile = File(...),
    id_colegio: int = Form(...),
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    if current_user["rol"] not in ["lawyer", "admin"]:
        raise HTTPException(status_code=403, detail="No tiene permisos para subir archivos")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        # Mapeo de columnas (puedes ajustar según tu excel)
        # Se asume que las columnas se llaman igual que en la imagen o similar
        # Normalizar nombres de columnas a minúsculas y quitar espacios para facilitar
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        required_cols = ["NOMBRE ESTUDIANTE", "CURSO", "CAUSA"]
        for col in required_cols:
            if col not in df.columns:
                raise HTTPException(status_code=400, detail=f"Falta la columna obligatoria: {col}")

        registros_creados = 0
        for index, row in df.iterrows():
            # Limpiar datos
            def get_val(col, default=None):
                val = row.get(col)
                if pd.isna(val): return default
                return val
            def get_str_val(col, default=""):
                val = row.get(col)
                if pd.isna(val): return default
                if isinstance(val, (datetime, pd.Timestamp)):
                    return val.strftime("%Y-%m-%d")
                val_str = str(val).strip()
                if val_str.endswith(" 00:00:00"):
                    return val_str.replace(" 00:00:00", "")
                return val_str

            # Procesar fechas (Pandas a Python date)
            def parse_date(col):
                val = row.get(col)
                if pd.isna(val): return None
                try:
                    return pd.to_datetime(val).date()
                except:
                    return None

            db_estudiante = models.Estudiante(
                rut=get_str_val("RUT"),
                nombre_estudiante=get_str_val("NOMBRE ESTUDIANTE"),
                curso=get_str_val("CURSO"),
                causa=get_str_val("CAUSA"),
                fecha_inicio_proceso=parse_date("FECHA INICIO PROCESO AULA SEGURA") or parse_date("FECHA INICIO"),
                descargos=get_str_val("DESCARGOS"),
                fecha_notificacion_medida=parse_date("FECHA NOTIFICACIÓN MEDIDA"),
                fecha_recepcion_apelacion=parse_date("FECHA RECEPCIÓN CARTA APELACIÓN") or parse_date("FECHA APELACIÓN"),
                fecha_consejo_profesores=parse_date("FECHA CONSEJO PROFESORES"),
                fecha_notificacion_final=parse_date("FECHA NOTIFICACIÓN FINAL \"MEDIDA\"") or parse_date("FECHA NOTIFICACIÓN FINAL"),
                fecha_envio_sie=parse_date("FECHA ENVÍO DE ANTECEDENTES SIE") or parse_date("FECHA ENVÍO SIE"),
                resultado_revision=get_str_val("RESULTADO REVISIÓN EXPEDIENTE"),
                medida=get_str_val("MEDIDA", "EXPULSIÓN"),
                id_colegio=int(get_val("ID COLEGIO", id_colegio)),
                id_usuario=current_user["id"]
            )
            db.add(db_estudiante)
            registros_creados += 1
            
        db.commit()
        return {"count": registros_creados, "message": "Carga masiva exitosa"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")


# --- GESTION DE USUARIOS Y CONTRASEÑAS ---

@app.post("/change-password")
def change_password(
    req: schemas.PasswordChange,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    user = db.query(models.Usuario).filter(models.Usuario.id == current_user["id"]).first()
    if not auth.verify_password(req.old_password, user.clave):
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta")
    
    user.clave = auth.get_password_hash(req.new_password)
    db.commit()
    return {"message": "Contraseña actualizada exitosamente"}

@app.get("/admin/users")
def list_users(
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    if current_user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    return db.query(models.Usuario).all()

@app.post("/admin/users")
def create_user(
    user_data: schemas.UserAdminCreate,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    if current_user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    # Verificar si el nombre ya existe
    existing = db.query(models.Usuario).filter(models.Usuario.nombre == user_data.nombre).first()
    if existing:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")

    db_user = models.Usuario(
        nombre=user_data.nombre,
        clave=auth.get_password_hash(user_data.clave),
        id_rol=user_data.id_rol,
        id_colegio=user_data.id_colegio,
        estado=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.put("/admin/users/{user_id}")
def update_user(
    user_id: int,
    user_data: schemas.UserAdminUpdate,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    if current_user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    db_user = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user_data.nombre: db_user.nombre = user_data.nombre
    if user_data.clave: db_user.clave = auth.get_password_hash(user_data.clave)
    if user_data.id_rol: db_user.id_rol = user_data.id_rol
    if user_data.id_colegio: db_user.id_colegio = user_data.id_colegio
    if user_data.estado is not None: db_user.estado = user_data.estado

    db.commit()
    return {"message": "Usuario actualizado"}

# --- DESTINATARIOS DE NOTIFICACIONES ---

def _require_editor(current_user):
    if current_user["rol"] not in ["lawyer", "admin"]:
        raise HTTPException(status_code=403, detail="No tiene permisos para esta acción")

def _grupos_de_destinatario(db, dest_id):
    rows = (
        db.query(models.Grupo)
        .join(models.DestinatarioGrupo, models.DestinatarioGrupo.grupo_id == models.Grupo.id)
        .filter(models.DestinatarioGrupo.destinatario_id == dest_id)
        .all()
    )
    return [{"id": g.id, "nombre": g.nombre} for g in rows]

def _dest_dict(db, d):
    return {
        "id": d.id,
        "nombre": d.nombre,
        "email": d.email,
        "id_colegio": d.id_colegio,
        "todos_colegios": d.todos_colegios,
        "estado": d.estado,
        "grupos": _grupos_de_destinatario(db, d.id),
    }

def _set_grupos(db, dest_id, grupo_ids):
    """Reemplaza la membresía de grupos de un destinatario."""
    db.query(models.DestinatarioGrupo).filter(
        models.DestinatarioGrupo.destinatario_id == dest_id
    ).delete()
    for gid in set(grupo_ids or []):
        db.add(models.DestinatarioGrupo(destinatario_id=dest_id, grupo_id=gid))
    db.commit()

@app.get("/destinatarios", response_model=List[schemas.Destinatario])
def list_destinatarios(
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    return [_dest_dict(db, d) for d in db.query(models.Destinatario).all()]

@app.post("/destinatarios", response_model=schemas.Destinatario)
def create_destinatario(
    data: schemas.DestinatarioCreate,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    payload = data.dict()
    grupo_ids = payload.pop("grupo_ids", None)
    db_dest = models.Destinatario(**payload)
    db.add(db_dest)
    db.commit()
    db.refresh(db_dest)
    if grupo_ids:
        _set_grupos(db, db_dest.id, grupo_ids)
    return _dest_dict(db, db_dest)

@app.put("/destinatarios/{dest_id}", response_model=schemas.Destinatario)
def update_destinatario(
    dest_id: int,
    data: schemas.DestinatarioUpdate,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    db_dest = db.query(models.Destinatario).filter(models.Destinatario.id == dest_id).first()
    if not db_dest:
        raise HTTPException(status_code=404, detail="Destinatario no encontrado")
    for key, value in data.dict(exclude_unset=True).items():
        setattr(db_dest, key, value)
    db.commit()
    db.refresh(db_dest)
    return _dest_dict(db, db_dest)

@app.post("/destinatarios/{dest_id}/grupos", response_model=schemas.Destinatario)
def set_grupos_destinatario(
    dest_id: int,
    data: schemas.GrupoIds,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    db_dest = db.query(models.Destinatario).filter(models.Destinatario.id == dest_id).first()
    if not db_dest:
        raise HTTPException(status_code=404, detail="Destinatario no encontrado")
    _set_grupos(db, dest_id, data.grupo_ids)
    return _dest_dict(db, db_dest)

@app.delete("/destinatarios/{dest_id}")
def delete_destinatario(
    dest_id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    db_dest = db.query(models.Destinatario).filter(models.Destinatario.id == dest_id).first()
    if not db_dest:
        raise HTTPException(status_code=404, detail="Destinatario no encontrado")
    db.query(models.DestinatarioGrupo).filter(
        models.DestinatarioGrupo.destinatario_id == dest_id
    ).delete()
    db.delete(db_dest)
    db.commit()
    return {"message": "Destinatario eliminado"}

@app.get("/estudiantes/{id}/destinatarios", response_model=List[schemas.Destinatario])
def destinatarios_de_estudiante(
    id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    """Lista a quiénes se enviaría la notificación de este estudiante (por defecto)."""
    _require_editor(current_user)
    estudiante = db.query(models.Estudiante).filter(models.Estudiante.id == id).first()
    if not estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    dests = (
        db.query(models.Destinatario)
        .filter(
            (models.Destinatario.id_colegio == estudiante.id_colegio)
            | (models.Destinatario.todos_colegios == True)
        )
        .all()
    )
    return [_dest_dict(db, d) for d in dests]

# --- GRUPOS DE DESTINATARIOS ---

@app.get("/grupos", response_model=List[schemas.Grupo])
def list_grupos(
    id_colegio: Optional[int] = None,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    q = db.query(models.Grupo).filter(models.Grupo.estado == True)
    if id_colegio is not None:
        q = q.filter(models.Grupo.id_colegio == id_colegio)
    return q.all()

@app.post("/grupos", response_model=schemas.Grupo)
def create_grupo(
    data: schemas.GrupoCreate,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    db_grupo = models.Grupo(nombre=data.nombre, id_colegio=data.id_colegio, estado=True)
    db.add(db_grupo)
    db.commit()
    db.refresh(db_grupo)
    return db_grupo

@app.put("/grupos/{grupo_id}", response_model=schemas.Grupo)
def update_grupo(
    grupo_id: int,
    data: schemas.GrupoUpdate,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    db_grupo = db.query(models.Grupo).filter(models.Grupo.id == grupo_id).first()
    if not db_grupo:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    for key, value in data.dict(exclude_unset=True).items():
        setattr(db_grupo, key, value)
    db.commit()
    db.refresh(db_grupo)
    return db_grupo

@app.delete("/grupos/{grupo_id}")
def delete_grupo(
    grupo_id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    db_grupo = db.query(models.Grupo).filter(models.Grupo.id == grupo_id).first()
    if not db_grupo:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    db.query(models.DestinatarioGrupo).filter(
        models.DestinatarioGrupo.grupo_id == grupo_id
    ).delete()
    db.delete(db_grupo)
    db.commit()
    return {"message": "Grupo eliminado"}

# --- PLANTILLAS DE CORREO (CUERPOS TIPO POR FASE) ---

@app.get("/plantillas", response_model=List[schemas.PlantillaCorreo])
def list_plantillas(
    etapa: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    q = db.query(models.PlantillaCorreo).filter(models.PlantillaCorreo.estado == True)
    if etapa:
        q = q.filter(models.PlantillaCorreo.etapa == etapa)
    return q.order_by(models.PlantillaCorreo.titulo.asc()).all()

@app.post("/plantillas", response_model=schemas.PlantillaCorreo)
def create_plantilla(
    data: schemas.PlantillaCorreoCreate,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    if not data.titulo.strip() or not data.cuerpo.strip():
        raise HTTPException(status_code=400, detail="El título y el cuerpo son obligatorios")
    db_pl = models.PlantillaCorreo(
        titulo=data.titulo.strip(),
        etapa=data.etapa or "inicio_proceso",
        cuerpo=data.cuerpo,
        estado=True,
    )
    db.add(db_pl)
    db.commit()
    db.refresh(db_pl)
    return db_pl

@app.put("/plantillas/{plantilla_id}", response_model=schemas.PlantillaCorreo)
def update_plantilla(
    plantilla_id: int,
    data: schemas.PlantillaCorreoUpdate,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    db_pl = db.query(models.PlantillaCorreo).filter(models.PlantillaCorreo.id == plantilla_id).first()
    if not db_pl:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    for key, value in data.dict(exclude_unset=True).items():
        setattr(db_pl, key, value)
    db.commit()
    db.refresh(db_pl)
    return db_pl

@app.delete("/plantillas/{plantilla_id}")
def delete_plantilla(
    plantilla_id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    db_pl = db.query(models.PlantillaCorreo).filter(models.PlantillaCorreo.id == plantilla_id).first()
    if not db_pl:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    db_pl.estado = False  # soft delete
    db.commit()
    return {"message": "Plantilla eliminada"}

@app.get("/estudiantes/{id}/grupos", response_model=List[schemas.Grupo])
def grupos_de_estudiante(
    id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    """Grupos disponibles para notificar a este estudiante (los de su colegio)."""
    _require_editor(current_user)
    estudiante = db.query(models.Estudiante).filter(models.Estudiante.id == id).first()
    if not estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    return (
        db.query(models.Grupo)
        .filter(
            models.Grupo.estado == True,
            models.Grupo.id_colegio == estudiante.id_colegio,
        )
        .all()
    )

# --- NOTIFICACIONES (RECORDATORIOS) ---

MODOS_VALIDOS = {
    "una_vez":        {"intervalo": 1, "max": 1},
    "paulatino":      {"intervalo": 1, "max": None},
    "cada_3_dias":    {"intervalo": 3, "max": 3},
    "fecha_indicada": {"intervalo": 1, "max": 1},
    "dias_habiles":   {"intervalo": 1, "max": None},
}

@app.post("/estudiantes/{id}/notificar")
def crear_notificacion(
    id: int,
    data: schemas.NotificacionCreate,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    estudiante = db.query(models.Estudiante).filter(models.Estudiante.id == id).first()
    if not estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    if data.modo not in MODOS_VALIDOS:
        raise HTTPException(status_code=400, detail="Modo de envío inválido")

    if data.modo == "fecha_indicada" and not data.fecha_programada:
        raise HTTPException(status_code=400, detail="Debe indicar la fecha de envío")

    if data.modo == "dias_habiles" and (not data.dias_habiles_total or not data.dias_habiles_envio):
        raise HTTPException(status_code=400, detail="Debe indicar el plazo total y los días de envío para el modo días hábiles")

    etapa = data.etapa or "inicio_proceso"

    # No duplicar: misma fase + misma fecha de envío/programación.
    # Inmediato/días hábiles -> hoy; 'fecha_indicada' -> la fecha programada.
    # Solo bloquean las notificaciones activas o completadas (las canceladas liberan la fase).
    fecha_nueva = data.fecha_programada if data.modo == "fecha_indicada" else datetime.now().date()
    existentes = (
        db.query(models.Notificacion)
        .filter(
            models.Notificacion.estudiante_id == id,
            models.Notificacion.etapa == etapa,
            models.Notificacion.estado.in_(["activo", "completado"]),
        )
        .all()
    )
    for ex in existentes:
        if ex.fecha_programada:
            f_ex = ex.fecha_programada
        elif ex.fecha_creacion:
            f_ex = ex.fecha_creacion.date() if hasattr(ex.fecha_creacion, "date") else ex.fecha_creacion
        else:
            f_ex = None
        if f_ex == fecha_nueva:
            raise HTTPException(
                status_code=409,
                detail="Ya existe una notificación de esta fase para esa fecha. Cancélala si necesitas enviarla de nuevo.",
            )

    # En la etapa 'medida' se guarda el estado elegido en el campo del estudiante
    if etapa == "medida" and data.medida:
        estudiante.medida = data.medida
        db.commit()

    grupo_ids_str = ",".join(str(g) for g in data.grupo_ids) if data.grupo_ids else None

    cfg = MODOS_VALIDOS[data.modo]
    notif = models.Notificacion(
        estudiante_id=id,
        id_usuario=current_user["id"],
        modo=data.modo,
        etapa=etapa,
        estado="activo",
        grupo_ids=grupo_ids_str,
        intervalo_dias=cfg["intervalo"],
        max_envios=cfg["max"],
        veces_enviado=0,
        fecha_programada=data.fecha_programada if data.modo == "fecha_indicada" else None,
        proximo_envio=datetime.now() if data.modo != "fecha_indicada" else None,
        cuerpo_personalizado=data.cuerpo_personalizado,
        asunto_personalizado=data.asunto_personalizado,
        dias_habiles_total=data.dias_habiles_total if data.modo == "dias_habiles" else None,
        dias_habiles_envio=data.dias_habiles_envio if data.modo == "dias_habiles" else None,
        hora_envio=data.hora_envio if data.modo == "dias_habiles" else None,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    # Los modos inmediatos envían el primer correo al instante; 'fecha_indicada' y 'dias_habiles'
    # quedan a cargo del scheduler.
    if data.modo == "fecha_indicada":
        return {
            "message": "Notificación programada",
            "notificacion_id": notif.id,
            "programada": True,
            "fecha_programada": str(data.fecha_programada),
        }

    if data.modo == "dias_habiles":
        # Materializar cada día de envío como una tarea en envios_programados
        # (día 1 = hoy + los días de la lista). Snapshot de destinatarios incluido.
        notifications.programar_envios_dias_habiles(db, notif, estudiante)
        # Enviar de inmediato los que ya estén vencidos (p. ej. el día 1 = hoy si pasó la hora).
        enviados, fallidos = notifications.enviar_programados_vencidos(db, notif.id)
        # Reflejar el próximo envío pendiente (o completar) en el registro del job.
        notifications._actualizar_notificacion_padre(db, notif.id)
        return {
            "message": "Notificación por días hábiles programada",
            "notificacion_id": notif.id,
            "programada": True,
            "dias_envio": data.dias_habiles_envio,
            "enviados": enviados,
            "fallidos": fallidos,
        }

    enviados, fallidos = notifications.procesar_notificacion(db, notif)
    return {
        "message": "Notificación enviada",
        "notificacion_id": notif.id,
        "enviados": enviados,
        "fallidos": fallidos,
    }

@app.get("/estudiantes/{id}/notificaciones", response_model=List[schemas.Notificacion])
def notificaciones_de_estudiante(
    id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    return (
        db.query(models.Notificacion)
        .filter(models.Notificacion.estudiante_id == id)
        .order_by(models.Notificacion.id.desc())
        .all()
    )

@app.post("/notificaciones/{notif_id}/cancelar")
def cancelar_notificacion(
    notif_id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    notif = db.query(models.Notificacion).filter(models.Notificacion.id == notif_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    notif.estado = "cancelado"
    notif.proximo_envio = None
    # Cancelar los envíos programados pendientes de esta notificación.
    db.query(models.EnvioProgramado).filter(
        models.EnvioProgramado.notificacion_id == notif_id,
        models.EnvioProgramado.estado == "pendiente",
    ).update({models.EnvioProgramado.estado: "cancelado"})
    db.commit()
    return {"message": "Notificación cancelada"}

@app.delete("/notificaciones/{notif_id}")
def eliminar_notificacion(
    notif_id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    """Elimina una notificación del historial (y sus logs/envíos). Libera la fase para volver a enviar."""
    _require_editor(current_user)
    notif = db.query(models.Notificacion).filter(models.Notificacion.id == notif_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    db.query(models.NotificacionLog).filter(
        models.NotificacionLog.notificacion_id == notif_id
    ).delete()
    db.query(models.EnvioProgramado).filter(
        models.EnvioProgramado.notificacion_id == notif_id
    ).delete()
    db.delete(notif)
    db.commit()
    return {"message": "Notificación eliminada"}

@app.get("/notificaciones/{notif_id}/envios", response_model=List[schemas.EnvioProgramado])
def envios_programados_de_notificacion(
    notif_id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    """Lista los envíos programados (una fila por día) de una notificación días hábiles."""
    _require_editor(current_user)
    return (
        db.query(models.EnvioProgramado)
        .filter(models.EnvioProgramado.notificacion_id == notif_id)
        .order_by(models.EnvioProgramado.fecha.asc())
        .all()
    )

@app.get("/notificaciones/{notif_id}/logs", response_model=List[schemas.NotificacionLog])
def logs_de_notificacion(
    notif_id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    _require_editor(current_user)
    return (
        db.query(models.NotificacionLog)
        .filter(models.NotificacionLog.notificacion_id == notif_id)
        .order_by(models.NotificacionLog.id.desc())
        .all()
    )

# --- CONSEJO DE PROFESORES ---

@app.get("/estudiantes/{id}/consejo")
def estado_consejo(
    id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    """Estado de confirmación del Consejo de Profesores y si ya se notificó."""
    _require_editor(current_user)
    estudiante = db.query(models.Estudiante).filter(models.Estudiante.id == id).first()
    if not estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    enviada = (
        db.query(models.Notificacion)
        .filter(
            models.Notificacion.estudiante_id == id,
            models.Notificacion.etapa == "consejo",
            models.Notificacion.veces_enviado > 0,
        )
        .order_by(models.Notificacion.id.desc())
        .first()
    )
    return {
        "confirmado": estudiante.consejo_confirmado,
        "fecha": estudiante.fecha_consejo_profesores,
        "correo_enviado": enviada is not None,
        "fecha_envio": enviada.ultimo_envio if enviada else None,
    }

@app.post("/estudiantes/{id}/consejo")
def registrar_consejo(
    id: int,
    data: schemas.ConsejoConfirmar,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user)
):
    """Registra la confirmación/cancelación del Consejo de Profesores.
    Opcionalmente envía un correo a los destinatarios (deja registro)."""
    _require_editor(current_user)
    estudiante = db.query(models.Estudiante).filter(models.Estudiante.id == id).first()
    if not estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    estudiante.consejo_confirmado = data.confirmado
    if data.fecha is not None:
        estudiante.fecha_consejo_profesores = data.fecha
    db.commit()

    correo_enviado = False
    enviados, fallidos = 0, 0

    if data.enviar_correo:
        grupo_ids_str = ",".join(str(g) for g in data.grupo_ids) if data.grupo_ids else None
        notif = models.Notificacion(
            estudiante_id=id,
            id_usuario=current_user["id"],
            modo="una_vez",
            etapa="consejo",
            estado="activo",
            grupo_ids=grupo_ids_str,
            intervalo_dias=1,
            max_envios=1,
            veces_enviado=0,
            proximo_envio=datetime.now(),
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        enviados, fallidos = notifications.procesar_notificacion(db, notif)
        correo_enviado = True

    return {
        "message": "Consejo registrado",
        "confirmado": data.confirmado,
        "correo_enviado": correo_enviado,
        "enviados": enviados,
        "fallidos": fallidos,
    }
