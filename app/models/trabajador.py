# models/trabajador.py — Trabajadores contratados por jornal.
# Un trabajador puede aparecer en múltiples temporadas.
# Sus pagos se registran en la tabla jornales (jornal.py).
from app import db

class Trabajador(db.Model):
    __tablename__ = 'trabajadores'

    id        = db.Column(db.Integer, primary_key=True)
    nombre    = db.Column(db.String(150), nullable=False)
    documento = db.Column(db.String(20), nullable=True)   # cédula, opcional
    telefono  = db.Column(db.String(20), nullable=True)
    activo    = db.Column(db.Boolean, default=True)       # False = no aparece en formularios nuevos

    # Relación inversa: historial completo de jornales del trabajador
    jornales = db.relationship('Jornal', backref='trabajador', lazy=True)

    def __repr__(self):
        return f'<Trabajador {self.nombre}>'
