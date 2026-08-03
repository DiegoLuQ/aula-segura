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

class EliminarLoteEnvios(BaseModel):
    ids: Optional[List[int]] = None
    eliminar_todos: bool = False
    estado_filtro: Optional[str] = None

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

class ConfigFaseBase(BaseModel):
    etapa: str
    nombre_etapa: str
    plazo_dias: int = 10
    dias_recordatorio: str = "0,3,5,7,9"
    id_colegio: Optional[int] = None

class ConfigFaseUpdate(BaseModel):
    plazo_dias: Optional[int] = None
    dias_recordatorio: Optional[str] = None

class ConfigFase(ConfigFaseBase):
    id: int
    fecha_actualizacion: Optional[datetime] = None

    class Config:
        from_attributes = True

class ConfigEmail(BaseModel):
    id: int
    envio_activo: bool = True
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    remitente_nombre: Optional[str] = "Aula Segura"
    remitente_email: Optional[str] = None
    fecha_actualizacion: Optional[datetime] = None

    class Config:
        from_attributes = True

class ConfigEmailUpdate(BaseModel):
    envio_activo: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: Optional[bool] = None
    remitente_nombre: Optional[str] = None
    remitente_email: Optional[str] = None

class TestEmailPayload(BaseModel):
    email_destino: str


    class Config:
        from_attributes = True

