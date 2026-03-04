from app import db
from datetime import datetime

class Movimiento(db.Model):
    __tablename__ = 'movimientos'

    id          = db.Column(db.Integer, primary_key=True)
    elemento_id = db.Column(db.Integer, db.ForeignKey('elementos_inventario.id'), nullable=False)
    tipo        = db.Column(db.Enum('entrada', 'salida'), nullable=False)
    cantidad    = db.Column(db.Numeric(10, 2), nullable=False)
    observacion = db.Column(db.Text, nullable=True)
    usuario_id  = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha       = db.Column(db.DateTime, default=datetime.now)

    # Relaciones
    usuario  = db.relationship('Usuario', backref='movimientos', lazy=True)

    def __repr__(self):
        return f'<Movimiento {self.tipo} - {self.cantidad}>'