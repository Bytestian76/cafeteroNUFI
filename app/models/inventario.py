from app import db

class ElementoInventario(db.Model):
    __tablename__ = 'elementos_inventario'

    id             = db.Column(db.Integer, primary_key=True)
    nombre         = db.Column(db.String(150), nullable=False)
    categoria      = db.Column(db.Enum('insumo', 'maquinaria', 'herramienta', 'material'), nullable=False)
    stock_actual   = db.Column(db.Numeric(10, 2), default=0)
    stock_minimo   = db.Column(db.Numeric(10, 2), default=0)
    unidad_medida  = db.Column(db.String(50), nullable=False)
    activo         = db.Column(db.Boolean, default=True)

    movimientos = db.relationship('Movimiento', backref='elemento', lazy=True)

    def tiene_alerta(self):
        """Retorna True si el stock actual está POR DEBAJO del mínimo (no igual)."""
        return self.stock_actual < self.stock_minimo

    def __repr__(self):
        return f'<Elemento {self.nombre}>'
