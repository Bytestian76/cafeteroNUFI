# models/usuario.py — Modelo de usuario del sistema.
# Campos: id, nombre, email (único), password_hash (bcrypt), activo, created_at.
# UserMixin provee is_authenticated, is_active y get_id() para Flask-Login.
from app import db, login_manager
from flask_login import UserMixin

# Flask-Login llama a esta función en cada request para recuperar el usuario de sesión
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'

    id            = db.Column(db.Integer, primary_key=True)
    nombre        = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)  # nunca se guarda el password en texto plano
    activo        = db.Column(db.Boolean, default=True)        # False = cuenta desactivada, no puede iniciar sesión
    created_at    = db.Column(db.DateTime, server_default=db.func.now())
