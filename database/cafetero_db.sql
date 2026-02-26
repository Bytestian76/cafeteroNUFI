-- ============================================================
--  EL CAFETERO DE NUFI — Script de Base de Datos
--  Sistema de Gestión Agrícola
--  Generado con base en el Documento Técnico v2
-- ============================================================

-- 1. CREAR Y SELECCIONAR LA BASE DE DATOS
-- ------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS cafetero_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE cafetero_db;

-- ============================================================
-- 2. TABLA: usuarios  (HU01 — Seguridad)
-- ============================================================
CREATE TABLE IF NOT EXISTS usuarios (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    nombre       VARCHAR(100)                        NOT NULL,
    email        VARCHAR(150)                        NOT NULL UNIQUE,
    password_hash VARCHAR(256)                       NOT NULL,
    rol          ENUM('admin','operario','consultor') NOT NULL DEFAULT 'operario',
    activo       BOOLEAN                             NOT NULL DEFAULT TRUE,
    created_at   DATETIME                            NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 3. TABLA: elementos_inventario  (HU02 — Inventario)
-- ============================================================
CREATE TABLE IF NOT EXISTS elementos_inventario (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    nombre         VARCHAR(150)                                          NOT NULL,
    categoria      ENUM('insumo','maquinaria','herramienta','material')  NOT NULL,
    stock_actual   DECIMAL(10,2)                                         NOT NULL DEFAULT 0.00,
    stock_minimo   DECIMAL(10,2)                                         NOT NULL DEFAULT 0.00,
    unidad_medida  VARCHAR(50)                                           NOT NULL,
    activo         BOOLEAN                                               NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 4. TABLA: movimientos  (HU03 — Movimientos)
-- ============================================================
CREATE TABLE IF NOT EXISTS movimientos (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    elemento_id  INT             NOT NULL,
    tipo         ENUM('entrada','salida') NOT NULL,
    cantidad     DECIMAL(10,2)   NOT NULL,
    observacion  TEXT,
    usuario_id   INT             NOT NULL,
    fecha        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_mov_elemento
        FOREIGN KEY (elemento_id) REFERENCES elementos_inventario(id),
    CONSTRAINT fk_mov_usuario
        FOREIGN KEY (usuario_id)  REFERENCES usuarios(id)
);

-- ============================================================
-- 5. TABLA: productos  (HU04 — Productos)
-- ============================================================
CREATE TABLE IF NOT EXISTS productos (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nombre          VARCHAR(150)    NOT NULL,
    descripcion     TEXT,
    precio_unitario DECIMAL(12,2)   NOT NULL DEFAULT 0.00,
    unidad_medida   VARCHAR(50)     NOT NULL,
    activo          BOOLEAN         NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 6. TABLA: clientes  (HU05 — Ventas)
-- ============================================================
CREATE TABLE IF NOT EXISTS clientes (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    nombre     VARCHAR(150)  NOT NULL,
    documento  VARCHAR(20),
    telefono   VARCHAR(20),
    direccion  VARCHAR(255)
);

-- ============================================================
-- 7. TABLA: ventas  (HU05 — Ventas)
-- ============================================================
CREATE TABLE IF NOT EXISTS ventas (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id  INT             NOT NULL,
    total       DECIMAL(14,2)   NOT NULL DEFAULT 0.00,
    fecha       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_venta_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);

-- ============================================================
-- 8. TABLA: detalle_ventas  (HU05 — Ventas)
-- ============================================================
CREATE TABLE IF NOT EXISTS detalle_ventas (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    venta_id     INT             NOT NULL,
    producto_id  INT             NOT NULL,
    cantidad     DECIMAL(10,2)   NOT NULL,
    precio_unit  DECIMAL(12,2)   NOT NULL,   -- precio fijo al momento de la venta
    subtotal     DECIMAL(14,2)   NOT NULL,   -- cantidad × precio_unit

    CONSTRAINT fk_det_venta
        FOREIGN KEY (venta_id)    REFERENCES ventas(id),
    CONSTRAINT fk_det_producto
        FOREIGN KEY (producto_id) REFERENCES productos(id)
);

-- ============================================================
-- 9. DATOS INICIALES — Usuario admin por defecto
--    Contraseña: admin123  (deberás cambiarla después)
--    Hash generado con bcrypt (12 rounds)
-- ============================================================
INSERT INTO usuarios (nombre, email, password_hash, rol, activo)
VALUES (
    'Administrador',
    'admin@cafetero.com',
    '$2b$12$KIXb9jVJn.JQFLFtRYOkVOSBRgn1PiM6gmCbRFZwScLJZUmAtMsXO',
    'admin',
    TRUE
);

-- ============================================================
-- 10. VERIFICACIÓN — Ver las tablas creadas
-- ============================================================
SHOW TABLES;
