from app import db

class Producto(db.Model):
    __tablename__ = 'productos'

    id              = db.Column(db.Integer, primary_key=True)
    nombre          = db.Column(db.String(150), nullable=False)
    descripcion     = db.Column(db.Text, nullable=True)
    precio_unitario = db.Column(db.Numeric(12, 2), nullable=False)
    unidad_medida   = db.Column(db.String(50), nullable=False)
    stock_actual    = db.Column(db.Numeric(10, 2), default=0)   # ← nuevo campo
    activo          = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Producto {self.nombre}>'
