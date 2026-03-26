# models/venta.py — Modelos de facturación: Cliente, Venta y DetalleVenta.
# Relaciones: Cliente 1→N Venta, Venta 1→N DetalleVenta, DetalleVenta N→1 Producto.
# La lógica de creación de facturas está en venta_controller.py línea 106.
# La lógica de anulación (restaurar stock) está en venta_controller.py línea 296.
from app import db
from datetime import datetime

class Cliente(db.Model):
    __tablename__ = 'clientes'

    id        = db.Column(db.Integer, primary_key=True)
    nombre    = db.Column(db.String(150), nullable=False)
    documento = db.Column(db.String(20), nullable=True)   # cédula o NIT, opcional
    telefono  = db.Column(db.String(20), nullable=True)
    direccion = db.Column(db.String(200), nullable=True)

    # Un cliente puede tener múltiples ventas; se usa en venta_controller.py para validar antes de eliminar
    ventas = db.relationship('Venta', backref='cliente', lazy=True)

    def __repr__(self):
        return f'<Cliente {self.nombre}>'


class Venta(db.Model):
    __tablename__ = 'ventas'

    id              = db.Column(db.Integer, primary_key=True)
    cliente_id      = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    subtotal        = db.Column(db.Numeric(14, 2), default=0)  # suma de detalles antes de IVA
    iva_porcentaje  = db.Column(db.Numeric(5, 2), default=0)   # 0, 5 o 19
    total           = db.Column(db.Numeric(14, 2), default=0)  # subtotal + IVA
    fecha           = db.Column(db.DateTime, default=datetime.now)
    anulada         = db.Column(db.Boolean, default=False)
    fecha_anulacion = db.Column(db.DateTime, nullable=True)
    campana_id      = db.Column(db.Integer, db.ForeignKey('temporadas.id'), nullable=True)  # opcional

    # detalles: lista de DetalleVenta asociados → usada en factura_pdf (venta_controller.py línea 318)
    detalles = db.relationship('DetalleVenta', backref='venta', lazy=True)

    def __repr__(self):
        return f'<Venta {self.id} - Total {self.total}>'


class DetalleVenta(db.Model):
    __tablename__ = 'detalle_ventas'

    id          = db.Column(db.Integer, primary_key=True)
    venta_id    = db.Column(db.Integer, db.ForeignKey('ventas.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad    = db.Column(db.Numeric(10, 2), nullable=False)
    precio_unit = db.Column(db.Numeric(12, 2), nullable=False)  # precio al momento de la venta (histórico)
    subtotal    = db.Column(db.Numeric(14, 2), nullable=False)  # cantidad * precio_unit

    producto = db.relationship('Producto', backref='detalles', lazy=True)

    def __repr__(self):
        return f'<DetalleVenta venta={self.venta_id} producto={self.producto_id}>'
