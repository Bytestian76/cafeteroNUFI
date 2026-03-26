# models/movimiento.py — Registro de entradas y salidas de inventario.
# tipo: 'entrada' suma al stock, 'salida' resta. Ambos actualizan ElementoInventario.stock_actual.
# valor: monto económico de la transacción (0 si es donación/regalo entre fincas).
# La lógica de actualización de stock está en movimiento_controller.py línea 103.
from app import db
from datetime import datetime

class Movimiento(db.Model):
    __tablename__ = 'movimientos'

    id          = db.Column(db.Integer, primary_key=True)
    elemento_id = db.Column(db.Integer, db.ForeignKey('elementos_inventario.id'), nullable=False)
    tipo        = db.Column(db.Enum('entrada', 'salida'), nullable=False)
    cantidad    = db.Column(db.Numeric(10, 2), nullable=False)
    valor       = db.Column(db.Numeric(14, 2), nullable=False, default=0)  # costo si entrada, ingreso si salida
    observacion = db.Column(db.Text, nullable=True)
    usuario_id  = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha       = db.Column(db.DateTime, default=datetime.now)

    campana_id  = db.Column(db.Integer, db.ForeignKey('temporadas.id'), nullable=True)  # opcional

    # Relaciones: elemento → ElementoInventario (backref definido en inventario.py)
    # campana → Temporada (backref definido en temporada.py)
    usuario = db.relationship('Usuario', backref='movimientos', lazy=True)

    def __repr__(self):
        return f'<Movimiento {self.tipo} - {self.cantidad}>'
