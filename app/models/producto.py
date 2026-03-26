# models/producto.py — Catálogo de productos para la venta.
# stock_actual se descuenta en venta_controller.py línea 161 al registrar una factura,
# y se restaura en venta_controller.py línea 308 al anular.
from app import db

class Producto(db.Model):
    __tablename__ = 'productos'

    id              = db.Column(db.Integer, primary_key=True)
    nombre          = db.Column(db.String(150), nullable=False)
    descripcion     = db.Column(db.Text, nullable=True)
    precio_unitario = db.Column(db.Numeric(12, 2), nullable=False)
    unidad_medida   = db.Column(db.String(50), nullable=False)
    stock_actual    = db.Column(db.Numeric(10, 2), default=0)
    activo          = db.Column(db.Boolean, default=True)  # False = no aparece en el formulario de facturas

    def __repr__(self):
        return f'<Producto {self.nombre}>'
