from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List

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
    consejo_confirmado: Optional[bool] = None

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

# --- DESTINATARIOS / NOTIFICACIONES ---

class GrupoMini(BaseModel):
    id: int
    nombre: str

    class Config:
        from_attributes = True

class GrupoCreate(BaseModel):
    nombre: str
    id_colegio: Optional[int] = None

class GrupoUpdate(BaseModel):
    nombre: Optional[str] = None
    id_colegio: Optional[int] = None
    estado: Optional[bool] = None

class Grupo(BaseModel):
    id: int
    nombre: str
    id_colegio: Optional[int] = None
    estado: bool = True

    class Config:
        from_attributes = True

class DestinatarioBase(BaseModel):
    nombre: str
    email: str
    id_colegio: Optional[int] = None
    todos_colegios: bool = False
    estado: bool = True

class DestinatarioCreate(DestinatarioBase):
    grupo_ids: Optional[List[int]] = None

class GrupoIds(BaseModel):
    grupo_ids: List[int] = []

class DestinatarioUpdate(BaseModel):
    nombre: Optional[str] = None
    email: Optional[str] = None
    id_colegio: Optional[int] = None
    todos_colegios: Optional[bool] = None
    estado: Optional[bool] = None

class Destinatario(DestinatarioBase):
    id: int
    grupos: List[GrupoMini] = []

    class Config:
        from_attributes = True

class NotificacionCreate(BaseModel):
    # modo: 'paulatino' | 'una_vez' | 'cada_3_dias' | 'fecha_indicada' | 'dias_habiles'
    modo: str
    # etapa: 'inicio_proceso' | 'medida'
    etapa: Optional[str] = "inicio_proceso"
    # medida/estado del proceso a guardar en el estudiante (solo etapa 'medida')
    medida: Optional[str] = None
    fecha_programada: Optional[date] = None
    # Grupos destino; None/vacío = todos los destinatarios del colegio
    grupo_ids: Optional[List[int]] = None
    cuerpo_personalizado: Optional[str] = None
    asunto_personalizado: Optional[str] = None
    dias_habiles_total: Optional[int] = None
    dias_habiles_envio: Optional[str] = None
    hora_envio: Optional[str] = None

class Notificacion(BaseModel):
    id: int
    estudiante_id: int
    id_usuario: int
    modo: str
    etapa: Optional[str] = "inicio_proceso"
    estado: str
    grupo_ids: Optional[str] = None
    intervalo_dias: int
    max_envios: Optional[int] = None
    veces_enviado: int
    proximo_envio: Optional[datetime] = None
    fecha_programada: Optional[date] = None
    ultimo_envio: Optional[datetime] = None
    cuerpo_personalizado: Optional[str] = None
    asunto_personalizado: Optional[str] = None
    dias_habiles_total: Optional[int] = None
    dias_habiles_envio: Optional[str] = None
    hora_envio: Optional[str] = None
    fecha_creacion: datetime

    class Config:
        from_attributes = True

class PlantillaCorreoBase(BaseModel):
    titulo: str
    etapa: str = "inicio_proceso"
    cuerpo: str

class PlantillaCorreoCreate(PlantillaCorreoBase):
    pass

class PlantillaCorreoUpdate(BaseModel):
    titulo: Optional[str] = None
    etapa: Optional[str] = None
    cuerpo: Optional[str] = None

class PlantillaCorreo(PlantillaCorreoBase):
    id: int
    fecha_creacion: datetime

    class Config:
        from_attributes = True

class EnvioProgramado(BaseModel):
    id: int
    notificacion_id: Optional[int] = None
    estudiante_id: int
    etapa: Optional[str] = None
    asunto: Optional[str] = None
    cuerpo: Optional[str] = None
    destinatarios: Optional[str] = None
    fecha: Optional[date] = None
    hora: Optional[str] = None
    dia_numero: Optional[int] = None
    estado: Optional[str] = None
    enviado: bool = False
    fecha_envio_real: Optional[datetime] = None

    class Config:
        from_attributes = True

class ConsejoConfirmar(BaseModel):
    confirmado: bool
    fecha: Optional[date] = None
    enviar_correo: bool = False
    grupo_ids: Optional[List[int]] = None

class NotificacionLog(BaseModel):
    id: int
    notificacion_id: int
    destinatario_email: str
    destinatario_nombre: Optional[str] = None
    exito: bool
    detalle: Optional[str] = None
    fecha_envio: datetime

    class Config:
        from_attributes = True
