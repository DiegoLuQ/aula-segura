-- Estructura de tablas para el sistema Aula Segura (Actualizado al modelo real del sistema)

-- 1. Tabla de Roles
CREATE TABLE IF NOT EXISTS pro_aula_segura_roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    rol VARCHAR(50) NOT NULL,
    estado TINYINT(1) DEFAULT 1
);

-- 2. Tabla de Colegios
CREATE TABLE IF NOT EXISTS pro_aula_segura_colegios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL
);

-- 3. Tabla de Usuarios
CREATE TABLE IF NOT EXISTS pro_aula_segura_usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    clave VARCHAR(255) NOT NULL,
    estado TINYINT(1) DEFAULT 1,
    id_rol INT,
    id_colegio INT,
    FOREIGN KEY (id_rol) REFERENCES pro_aula_segura_roles(id),
    FOREIGN KEY (id_colegio) REFERENCES pro_aula_segura_colegios(id)
);

-- 4. Tabla de Estudiantes
CREATE TABLE IF NOT EXISTS pro_aula_segura_estudiantes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    rut VARCHAR(20) NULL,
    nombre_estudiante VARCHAR(255) NULL,
    curso VARCHAR(100) NULL,
    causa TEXT NULL,
    fecha_inicio_proceso DATE NULL,
    descargos TEXT NULL,
    fecha_notificacion_medida DATE NULL,
    fecha_recepcion_apelacion DATE NULL,
    fecha_consejo_profesores DATE NULL,
    fecha_notificacion_final DATE NULL,
    fecha_envio_sie DATE NULL,
    resultado_revision TEXT NULL,
    medida VARCHAR(100) NULL,
    fecha_descargados DATE NULL,
    id_colegio INT NULL,
    id_usuario INT NULL,
    estado TINYINT(1) DEFAULT 1,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_colegio) REFERENCES pro_aula_segura_colegios(id),
    FOREIGN KEY (id_usuario) REFERENCES pro_aula_segura_usuarios(id)
);

-- 5. Tabla de Documentos para Estudiantes (PDFs de cargos, notificaciones, etc.)
CREATE TABLE IF NOT EXISTS pro_aula_segura_documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    estudiante_id INT NOT NULL,
    tipo VARCHAR(100) NULL,
    nombre_archivo VARCHAR(255) NULL,
    ruta_archivo VARCHAR(255) NULL,
    tamanio VARCHAR(50) NULL,
    fecha_subida DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (estudiante_id) REFERENCES pro_aula_segura_estudiantes(id) ON DELETE CASCADE
);

-- 6. Tabla de Otras Medidas (Procedimiento alternativo)
CREATE TABLE IF NOT EXISTS pro_aula_segura_otras_medidas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    rut VARCHAR(20) NULL,
    nombre_estudiante VARCHAR(255) NULL,
    curso VARCHAR(100) NULL,
    fecha_inicio DATE NULL,
    causa TEXT NULL,
    medida VARCHAR(100) NULL,
    id_colegio INT NULL,
    id_usuario INT NULL,
    estado TINYINT(1) DEFAULT 1,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_colegio) REFERENCES pro_aula_segura_colegios(id),
    FOREIGN KEY (id_usuario) REFERENCES pro_aula_segura_usuarios(id)
);

-- 7. Tabla de Documentos para Otras Medidas
CREATE TABLE IF NOT EXISTS pro_aula_segura_documentos_otras_medidas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    otra_medida_id INT NOT NULL,
    tipo VARCHAR(100) NULL,
    nombre_archivo VARCHAR(255) NULL,
    ruta_archivo VARCHAR(255) NULL,
    tamanio VARCHAR(50) NULL,
    fecha_subida DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (otra_medida_id) REFERENCES pro_aula_segura_otras_medidas(id) ON DELETE CASCADE
);

-- Inserción de datos iniciales sugeridos
INSERT INTO pro_aula_segura_roles (rol) VALUES ('lawyer'), ('viewer') ON DUPLICATE KEY UPDATE rol=rol;
