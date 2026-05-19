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
import models, schemas, auth, database

app = FastAPI(title="Sistema Aula Segura API")

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
