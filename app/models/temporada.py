# models/temporada.py — Ciclo productivo completo (siembra → venta).
# Conecta movimientos de inventario con ventas para calcular rentabilidad real por temporada.
# La restricción de temporada única activa se controla en campana_controller.py.
from app import db
from datetime import date as date_type


class Temporada(db.Model):
    __tablename__ = 'temporadas'

    id                   = db.Column(db.Integer, primary_key=True)
    nombre               = db.Column(db.String(150), nullable=False)
    descripcion          = db.Column(db.Text, nullable=True)
    fecha_inicio         = db.Column(db.Date, nullable=False)
    fecha_fin            = db.Column(db.Date, nullable=True)   # None = temporada activa
    estado               = db.Column(db.Enum('activa', 'cerrada'), nullable=False, default='activa')
    presupuesto_inicial  = db.Column(db.Numeric(14, 2), nullable=False, default=0)  # capital base de la temporada
    usuario_id           = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)

    # Relaciones inversas: movimientos, ventas y jornales asociados a esta temporada
    usuario     = db.relationship('Usuario', backref='temporadas', lazy=True)
    movimientos = db.relationship('Movimiento', backref='campana', lazy=True)
    ventas      = db.relationship('Venta', backref='campana', lazy=True)
    jornales    = db.relationship('Jornal', backref='campana', lazy=True)

    @property
    def costo_total(self):
        """Costos totales = movimientos de entrada + pagos de jornales → costo_mano_obra."""
        costo_insumos  = float(sum(m.valor for m in self.movimientos if m.tipo == 'entrada'))
        costo_jornales = float(sum(j.total for j in self.jornales))
        return costo_insumos + costo_jornales

    @property
    def costo_mano_obra(self):
        """Suma solo de jornales → permite desglosar mano de obra en el detalle de la temporada."""
        return float(sum(j.total for j in self.jornales))

    @property
    def ingreso_ventas(self):
        """Suma de ventas no anuladas asociadas → ingresos por producto final."""
        return float(sum(v.total for v in self.ventas if not v.anulada))

    @property
    def ingreso_salidas(self):
        """Suma de movimientos de salida con valor > 0 → venta de insumos o maquinaria usada."""
        return float(sum(m.valor for m in self.movimientos if m.tipo == 'salida' and m.valor > 0))

    @property
    def balance(self):
        """Rentabilidad = (ingresos ventas + ingresos salidas) - costos totales."""
        return (self.ingreso_ventas + self.ingreso_salidas) - self.costo_total

    @property
    def presupuesto_disponible(self):
        """Capital restante = presupuesto inicial - costos ejecutados hasta ahora."""
        return float(self.presupuesto_inicial or 0) - self.costo_total

    def __repr__(self):
        return f'<Temporada {self.nombre}>'
