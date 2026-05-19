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
