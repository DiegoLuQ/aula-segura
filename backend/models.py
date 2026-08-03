from datetime import datetime
from sqlalchemy import Column, Integer, String, Date, Text, ForeignKey, Boolean, DateTime, TIMESTAMP, func
from database import Base

class Rol(Base):
    __tablename__ = "pro_aula_segura_roles"
    id = Column(Integer, primary_key=True, index=True)
    rol = Column(String(50), nullable=False)
    estado = Column(Boolean, default=True)

class Colegio(Base):
    __tablename__ = "pro_aula_segura_colegios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)

class Usuario(Base):
    __tablename__ = "pro_aula_segura_usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    clave = Column(String(255), nullable=False)
    estado = Column(Boolean, default=True)
    id_rol = Column(Integer, ForeignKey("pro_aula_segura_roles.id"))
    id_colegio = Column(Integer, ForeignKey("pro_aula_segura_colegios.id"))

class Estudiante(Base):
    __tablename__ = "pro_aula_segura_estudiantes"
    id = Column(Integer, primary_key=True, index=True)
    rut = Column(String(20), nullable=True)
    nombre_estudiante = Column(String(255), nullable=True)
    curso = Column(String(100), nullable=True)
    causa = Column(Text, nullable=True)
    fecha_inicio_proceso = Column(Date)
    descargos = Column(Text)
    fecha_notificacion_medida = Column(Date)
    fecha_recepcion_apelacion = Column(Date)
    fecha_consejo_profesores = Column(Date)
    fecha_notificacion_final = Column(Date)
    fecha_envio_sie = Column(Date)
    resultado_revision = Column(Text)
    medida = Column(String(100))
    fecha_descargados = Column(Date)
    # Confirmación del Consejo de Profesores: True=confirmado, False=cancelado, None=sin registrar
    consejo_confirmado = Column(Boolean, nullable=True)
    id_colegio = Column(Integer, ForeignKey("pro_aula_segura_colegios.id"))
    id_usuario = Column(Integer, ForeignKey("pro_aula_segura_usuarios.id"))
    estado = Column(Boolean, default=True)
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())

class Documento(Base):
    __tablename__ = "pro_aula_segura_documentos"
    id = Column(Integer, primary_key=True, index=True)
    estudiante_id = Column(Integer, ForeignKey("pro_aula_segura_estudiantes.id"))
    tipo = Column(String(100))
    nombre_archivo = Column(String(255))
    ruta_archivo = Column(String(255))
    tamanio = Column(String(50)) # Peso del archivo (KB, MB)
    fecha_subida = Column(DateTime, default=datetime.now)

class OtraMedida(Base):
    __tablename__ = "pro_aula_segura_otras_medidas"
    id = Column(Integer, primary_key=True, index=True)
    rut = Column(String(20), nullable=True)
    nombre_estudiante = Column(String(255), nullable=True)
    curso = Column(String(100), nullable=True)
    fecha_inicio = Column(Date)
    causa = Column(Text, nullable=True)
    medida = Column(String(100))
    id_colegio = Column(Integer, ForeignKey("pro_aula_segura_colegios.id"))
    id_usuario = Column(Integer, ForeignKey("pro_aula_segura_usuarios.id"))
    estado = Column(Boolean, default=True)
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())

class DocumentoOtraMedida(Base):
    __tablename__ = "pro_aula_segura_documentos_otras_medidas"
    id = Column(Integer, primary_key=True, index=True)
    otra_medida_id = Column(Integer, ForeignKey("pro_aula_segura_otras_medidas.id"))
    tipo = Column(String(100))
    nombre_archivo = Column(String(255))
    ruta_archivo = Column(String(255))
    tamanio = Column(String(50))
    fecha_subida = Column(DateTime, default=datetime.now)

class Destinatario(Base):
    """Personas que reciben las notificaciones de los procesos."""
    __tablename__ = "pro_aula_segura_destinatarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    email = Column(String(255), nullable=False)
    id_colegio = Column(Integer, ForeignKey("pro_aula_segura_colegios.id"), nullable=True)
    # Privilegio: si es True recibe correos de TODOS los colegios
    todos_colegios = Column(Boolean, default=False)
    # estado = si está activo (se le envían correos) o no
    estado = Column(Boolean, default=True)
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())

class Grupo(Base):
    """Grupo/equipo de destinatarios (por colegio)."""
    __tablename__ = "pro_aula_segura_grupos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    id_colegio = Column(Integer, ForeignKey("pro_aula_segura_colegios.id"), nullable=True)
    estado = Column(Boolean, default=True)
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())

class DestinatarioGrupo(Base):
    """Membresía muchos-a-muchos entre destinatarios y grupos."""
    __tablename__ = "pro_aula_segura_destinatario_grupo"
    id = Column(Integer, primary_key=True, index=True)
    destinatario_id = Column(Integer, ForeignKey("pro_aula_segura_destinatarios.id"))
    grupo_id = Column(Integer, ForeignKey("pro_aula_segura_grupos.id"))

class Notificacion(Base):
    """Trabajo de envío de recordatorios asociado a un estudiante."""
    __tablename__ = "pro_aula_segura_notificaciones"
    id = Column(Integer, primary_key=True, index=True)
    estudiante_id = Column(Integer, ForeignKey("pro_aula_segura_estudiantes.id"))
    id_usuario = Column(Integer, ForeignKey("pro_aula_segura_usuarios.id"))  # quién la activó
    # Grupos destino (ids separados por coma). Vacío/None = todos los del colegio.
    grupo_ids = Column(String(255), nullable=True)
    # modo: 'paulatino' | 'una_vez' | 'cada_3_dias' | 'fecha_indicada'
    modo = Column(String(30), nullable=False)
    # etapa: 'inicio_proceso' | 'medida'
    etapa = Column(String(30), default="inicio_proceso")
    # estado: 'activo' | 'completado' | 'cancelado'
    estado = Column(String(20), default="activo")
    intervalo_dias = Column(Integer, default=1)
    max_envios = Column(Integer, nullable=True)   # None = ilimitado (paulatino)
    veces_enviado = Column(Integer, default=0)
    proximo_envio = Column(DateTime, nullable=True)
    fecha_programada = Column(Date, nullable=True)  # solo para 'fecha_indicada'
    ultimo_envio = Column(DateTime, nullable=True)
    cuerpo_personalizado = Column(Text, nullable=True)
    dias_habiles_total = Column(Integer, nullable=True)
    dias_habiles_envio = Column(String(255), nullable=True)
    hora_envio = Column(String(5), nullable=True)  # 'HH:MM' para envíos programados (días hábiles)
    asunto_personalizado = Column(String(255), nullable=True)  # asunto editable del correo
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())

class PlantillaCorreo(Base):
    """Plantillas reutilizables de cuerpo de correo, organizadas por etapa (globales)."""
    __tablename__ = "pro_aula_segura_plantillas"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(150), nullable=False)
    # etapa: 'inicio_proceso' | 'medida' | 'apelacion' | 'consejo' | 'final_medida'
    etapa = Column(String(30), nullable=False, default="inicio_proceso")
    cuerpo = Column(Text, nullable=False)
    estado = Column(Boolean, default=True)
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())

class EnvioProgramado(Base):
    """Cada envío individual de una notificación 'días hábiles', materializado como tarea.

    Una notificación 'días hábiles' genera varias filas aquí: una por cada día de envío,
    con la fecha y hora exactas, el cuerpo, el tipo (etapa) y los destinatarios congelados.
    """
    __tablename__ = "pro_aula_segura_envios_programados"
    id = Column(Integer, primary_key=True, index=True)
    notificacion_id = Column(Integer, ForeignKey("pro_aula_segura_notificaciones.id"))
    estudiante_id = Column(Integer, ForeignKey("pro_aula_segura_estudiantes.id"))
    etapa = Column(String(30))                    # tipo de correo
    asunto = Column(String(255), nullable=True)   # asunto del correo (snapshot)
    cuerpo = Column(Text, nullable=True)          # cuerpo del correo (con placeholders)
    destinatarios = Column(Text, nullable=True)   # snapshot JSON: [{"nombre","email"}]
    fecha = Column(Date)                          # fecha del envío
    hora = Column(String(5))                      # 'HH:MM'
    dia_numero = Column(Integer, nullable=True)   # qué día del plan (1, 2, 3, 6...)
    estado = Column(String(20), default="pendiente")  # pendiente | enviado | cancelado
    enviado = Column(Boolean, default=False)
    fecha_envio_real = Column(DateTime, nullable=True)
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())

class NotificacionLog(Base):
    """Registro de cada correo enviado (para ver el estado de envío)."""
    __tablename__ = "pro_aula_segura_notificaciones_log"
    id = Column(Integer, primary_key=True, index=True)
    notificacion_id = Column(Integer, ForeignKey("pro_aula_segura_notificaciones.id"))
    estudiante_id = Column(Integer, ForeignKey("pro_aula_segura_estudiantes.id"))
    destinatario_email = Column(String(255))
    destinatario_nombre = Column(String(150))
    exito = Column(Boolean, default=False)
    detalle = Column(String(255), nullable=True)
    fecha_envio = Column(DateTime, default=datetime.now)

class ConfigFase(Base):
    """Configuración de plazo y días de recordatorio por etapa del proceso disciplinario."""
    __tablename__ = "pro_aula_segura_config_fases"
    id = Column(Integer, primary_key=True, index=True)
    etapa = Column(String(50), nullable=False)
    nombre_etapa = Column(String(100), nullable=False)
    plazo_dias = Column(Integer, default=10)
    dias_recordatorio = Column(String(255), default="0,3,5,7,9")  # Comas separadas, ej: "0,5,7,9"
    id_colegio = Column(Integer, ForeignKey("pro_aula_segura_colegios.id"), nullable=True)
    fecha_actualizacion = Column(TIMESTAMP, server_default=func.now())


class ConfigEmail(Base):
    """Configuración global de la arquitectura de envíos de correo del sistema."""
    __tablename__ = "pro_aula_segura_config_email"
    id = Column(Integer, primary_key=True, index=True)
    envio_activo = Column(Boolean, default=True)  # Switch general ON/OFF
    smtp_host = Column(String(150), nullable=True)
    smtp_port = Column(Integer, default=587)
    smtp_user = Column(String(150), nullable=True)
    smtp_password = Column(String(150), nullable=True)
    smtp_use_tls = Column(Boolean, default=True)
    remitente_nombre = Column(String(100), default="Aula Segura")
    remitente_email = Column(String(150), nullable=True)
    fecha_actualizacion = Column(TIMESTAMP, server_default=func.now())


