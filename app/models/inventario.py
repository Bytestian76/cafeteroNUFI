# models/inventario.py — Modelo de elemento de inventario.
# Categorías válidas: insumo, maquinaria, herramienta, material.
# La propiedad tiene_alerta es usada en el dashboard (auth_controller.py línea 78)
# y en la vista lista.html para mostrar badges de escasez.
from app import db

class ElementoInventario(db.Model):
    __tablename__ = 'elementos_inventario'

    id            = db.Column(db.Integer, primary_key=True)
    nombre        = db.Column(db.String(150), nullable=False)
    categoria     = db.Column(db.Enum('insumo', 'maquinaria', 'herramienta', 'material'), nullable=False)
    stock_actual  = db.Column(db.Numeric(10, 2), default=0)
    stock_minimo  = db.Column(db.Numeric(10, 2), default=0)
    unidad_medida = db.Column(db.String(50), nullable=False)
    activo        = db.Column(db.Boolean, default=True)  # False = oculto en listados, sin alertas

    # Relación inversa: movimiento_controller.py usa elemento.movimientos para validar antes de eliminar
    movimientos = db.relationship('Movimiento', backref='elemento', lazy=True)

    @property
    def tiene_alerta(self):
        """Retorna True si el stock actual está POR DEBAJO del mínimo (no igual)."""
        return self.stock_actual < self.stock_minimo

    def __repr__(self):
        return f'<Elemento {self.nombre}>'
