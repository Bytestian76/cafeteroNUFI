-- ============================================================
--  EL CAFETERO DE NUFI — Script de Base de Datos
--  Sistema de Gestión Agrícola
--  Última actualización: 2026-03-25
--  Estado: sincronizado con migraciones hasta d4e5f6a7b8c9
-- ============================================================

-- 1. CREAR Y SELECCIONAR LA BASE DE DATOS
-- ------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS cafetero_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE cafetero_db;

-- ============================================================
-- 2. TABLA: usuarios
-- ============================================================
CREATE TABLE IF NOT EXISTS usuarios (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    nombre        VARCHAR(100)  NOT NULL,
    email         VARCHAR(150)  NOT NULL UNIQUE,
    password_hash VARCHAR(256)  NOT NULL,
    activo        BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
    -- NOTA: la columna 'rol' fue eliminada en migración 0b5fea128ef2
);

-- ============================================================
-- 3. TABLA: elementos_inventario
-- ============================================================
CREATE TABLE IF NOT EXISTS elementos_inventario (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    nombre        VARCHAR(150)                                         NOT NULL,
    categoria     ENUM('insumo','maquinaria','herramienta','material') NOT NULL,
    stock_actual  DECIMAL(10,2)                                        NOT NULL DEFAULT 0.00,
    stock_minimo  DECIMAL(10,2)                                        NOT NULL DEFAULT 0.00,
    unidad_medida VARCHAR(50)                                          NOT NULL,
    activo        BOOLEAN                                              NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 4. TABLA: temporadas
--    Debe crearse antes de movimientos y ventas (FK dependency)
-- ============================================================
CREATE TABLE IF NOT EXISTS temporadas (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    nombre              VARCHAR(150)              NOT NULL,
    descripcion         TEXT,
    fecha_inicio        DATE                      NOT NULL,
    fecha_fin           DATE,                                  -- NULL = campaña activa
    estado              ENUM('activa','cerrada')  NOT NULL DEFAULT 'activa',
    presupuesto_inicial DECIMAL(14,2)             NOT NULL DEFAULT 0.00,
    usuario_id          INT                       NOT NULL,

    CONSTRAINT fk_campana_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- ============================================================
-- 5. TABLA: movimientos
-- ============================================================
CREATE TABLE IF NOT EXISTS movimientos (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    elemento_id INT             NOT NULL,
    tipo        ENUM('entrada','salida') NOT NULL,
    cantidad    DECIMAL(10,2)   NOT NULL,
    valor       DECIMAL(14,2)   NOT NULL DEFAULT 0.00,  -- costo si entrada, ingreso si salida; 0 = donación
    observacion TEXT,
    usuario_id  INT             NOT NULL,
    fecha       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    campana_id  INT,                                    -- NULL = movimiento fuera de campaña

    CONSTRAINT fk_mov_elemento
        FOREIGN KEY (elemento_id) REFERENCES elementos_inventario(id),
    CONSTRAINT fk_mov_usuario
        FOREIGN KEY (usuario_id)  REFERENCES usuarios(id),
    CONSTRAINT fk_mov_campana
        FOREIGN KEY (campana_id)  REFERENCES temporadas(id)
);

-- ============================================================
-- 6. TABLA: productos
-- ============================================================
CREATE TABLE IF NOT EXISTS productos (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nombre          VARCHAR(150)  NOT NULL,
    descripcion     TEXT,
    precio_unitario DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    unidad_medida   VARCHAR(50)   NOT NULL,
    stock_actual    DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    activo          BOOLEAN       NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 7. TABLA: clientes
-- ============================================================
CREATE TABLE IF NOT EXISTS clientes (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    nombre    VARCHAR(150)  NOT NULL,
    documento VARCHAR(20),
    telefono  VARCHAR(20),
    direccion VARCHAR(255)
);

-- ============================================================
-- 8. TABLA: ventas
-- ============================================================
CREATE TABLE IF NOT EXISTS ventas (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id      INT           NOT NULL,
    subtotal        DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    iva_porcentaje  DECIMAL(5,2)  NOT NULL DEFAULT 0.00,  -- valores esperados: 0, 5 o 19
    total           DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    fecha           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    anulada         BOOLEAN       NOT NULL DEFAULT FALSE,
    fecha_anulacion DATETIME,                              -- NULL = no anulada
    campana_id      INT,                                   -- NULL = venta fuera de campaña

    CONSTRAINT fk_venta_cliente
        FOREIGN KEY (cliente_id)  REFERENCES clientes(id),
    CONSTRAINT fk_venta_campana
        FOREIGN KEY (campana_id)  REFERENCES temporadas(id)
);

-- ============================================================
-- 9. TABLA: detalle_ventas
-- ============================================================
CREATE TABLE IF NOT EXISTS detalle_ventas (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    venta_id    INT           NOT NULL,
    producto_id INT           NOT NULL,
    cantidad    DECIMAL(10,2) NOT NULL,
    precio_unit DECIMAL(12,2) NOT NULL,   -- precio fijo al momento de la venta (histórico)
    subtotal    DECIMAL(14,2) NOT NULL,   -- cantidad × precio_unit

    CONSTRAINT fk_det_venta
        FOREIGN KEY (venta_id)    REFERENCES ventas(id),
    CONSTRAINT fk_det_producto
        FOREIGN KEY (producto_id) REFERENCES productos(id)
);

-- ============================================================
-- 10. TABLA: trabajadores
-- ============================================================
CREATE TABLE IF NOT EXISTS trabajadores (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    nombre    VARCHAR(150) NOT NULL,
    documento VARCHAR(20),
    telefono  VARCHAR(20),
    activo    BOOLEAN      NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 11. TABLA: jornales
-- ============================================================
CREATE TABLE IF NOT EXISTS jornales (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    trabajador_id     INT           NOT NULL,
    campana_id        INT           NOT NULL,
    fecha             DATE          NOT NULL,
    cantidad_jornales DECIMAL(6,2)  NOT NULL,
    valor_jornal      DECIMAL(10,2) NOT NULL,
    total             DECIMAL(14,2) NOT NULL,   -- cantidad_jornales × valor_jornal (histórico)
    observacion       TEXT,
    usuario_id        INT           NOT NULL,

    CONSTRAINT fk_jornal_trabajador FOREIGN KEY (trabajador_id) REFERENCES trabajadores(id),
    CONSTRAINT fk_jornal_campana    FOREIGN KEY (campana_id)    REFERENCES temporadas(id),
    CONSTRAINT fk_jornal_usuario    FOREIGN KEY (usuario_id)    REFERENCES usuarios(id)
);

-- ============================================================
-- 12. DATOS INICIALES — Usuario admin por defecto
--     Contraseña: admin123  (cambiar después del primer login)
--     Hash generado con bcrypt (12 rounds)
-- ============================================================
INSERT INTO usuarios (nombre, email, password_hash, activo)
VALUES (
    'Administrador',
    'admin@cafetero.com',
    '$2b$12$KIXb9jVJn.JQFLFtRYOkVOSBRgn1PiM6gmCbRFZwScLJZUmAtMsXO',
    TRUE
);

-- ============================================================
-- 13. VERIFICACIÓN
-- ============================================================
SHOW TABLES;
