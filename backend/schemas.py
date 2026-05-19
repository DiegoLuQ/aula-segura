from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    colegio_id: Optional[int] = None

class LoginRequest(BaseModel):
    nombre: str
    clave: str

class EstudianteBase(BaseModel):
    rut: Optional[str] = None
    nombre_estudiante: Optional[str] = None
    curso: Optional[str] = None
    causa: Optional[str] = None
    fecha_inicio_proceso: Optional[date] = None
    descargos: Optional[str] = None
    fecha_notificacion_medida: Optional[date] = None
    fecha_recepcion_apelacion: Optional[date] = None
    fecha_consejo_profesores: Optional[date] = None
    fecha_notificacion_final: Optional[date] = None
    fecha_envio_sie: Optional[date] = None
    resultado_revision: Optional[str] = None
    medida: Optional[str] = None
    fecha_descargados: Optional[date] = None
    id_colegio: Optional[int] = None

class EstudianteCreate(EstudianteBase):
    pass

class Estudiante(EstudianteBase):
    id: int
    id_usuario: int
    estado: bool
    fecha_creacion: datetime

    class Config:
        from_attributes = True

class DocumentoBase(BaseModel):
    tipo: str
    nombre_archivo: str
    tamanio: Optional[str] = None
    fecha_subida: datetime

class DocumentoCreate(DocumentoBase):
    estudiante_id: int
    ruta_archivo: str

class Documento(DocumentoBase):
    id: int
    estudiante_id: int
    ruta_archivo: str

    class Config:
        from_attributes = True

class UsuarioResponse(BaseModel):
    id: int
    nombre: str
    rol: str
    id_colegio: int

    class Config:
        from_attributes = True

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

class UserAdminCreate(BaseModel):
    nombre: str
    clave: str
    id_rol: int
    id_colegio: int

class UserAdminUpdate(BaseModel):
    nombre: Optional[str] = None
    clave: Optional[str] = None
    id_rol: Optional[int] = None
    id_colegio: Optional[int] = None
    estado: Optional[bool] = None

class OtraMedidaBase(BaseModel):
    rut: Optional[str] = None
    nombre_estudiante: Optional[str] = None
    curso: Optional[str] = None
    fecha_inicio: Optional[date] = None
    causa: Optional[str] = None
    medida: Optional[str] = None
    id_colegio: Optional[int] = None

class OtraMedidaCreate(OtraMedidaBase):
    pass

class OtraMedida(OtraMedidaBase):
    id: int
    id_usuario: int
    estado: bool
    fecha_creacion: datetime

    class Config:
        from_attributes = True

class DocumentoOtraMedidaBase(BaseModel):
    tipo: str
    nombre_archivo: str
    tamanio: Optional[str] = None
    fecha_subida: datetime

class DocumentoOtraMedidaCreate(DocumentoOtraMedidaBase):
    otra_medida_id: int
    ruta_archivo: str

class DocumentoOtraMedida(DocumentoOtraMedidaBase):
    id: int
    otra_medida_id: int
    ruta_archivo: str

    class Config:
        from_attributes = True
