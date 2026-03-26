# models/jornal.py — Registro de pago por jornal a un trabajador en una temporada.
# total se calcula como cantidad_jornales × valor_jornal y se guarda en DB para histórico.
# La relación con Temporada está definida en temporada.py (backref='jornales').
from app import db
from datetime import date as date_type

class Jornal(db.Model):
    __tablename__ = 'jornales'

    id                = db.Column(db.Integer, primary_key=True)
    trabajador_id     = db.Column(db.Integer, db.ForeignKey('trabajadores.id'), nullable=False)
    campana_id        = db.Column(db.Integer, db.ForeignKey('temporadas.id'), nullable=False)
    fecha             = db.Column(db.Date, nullable=False, default=date_type.today)
    cantidad_jornales = db.Column(db.Numeric(6, 2), nullable=False)   # puede ser 0.5 (medio día)
    valor_jornal      = db.Column(db.Numeric(10, 2), nullable=False)  # precio por jornal ese día
    total             = db.Column(db.Numeric(14, 2), nullable=False)  # cantidad × valor, guardado como histórico
    observacion       = db.Column(db.Text, nullable=True)
    usuario_id        = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)

    usuario = db.relationship('Usuario', backref='jornales', lazy=True)

    def __repr__(self):
        return f'<Jornal {self.trabajador_id} - {self.fecha} - ${self.total}>'
