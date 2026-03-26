# config.py — Configuración central de Flask.
# Lee variables de entorno desde el archivo .env (ver .env.example).
# SECRET_KEY y DATABASE_URL son obligatorias para que la app funcione.
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'clave_por_defecto')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True          # activa CSRF globalmente
    WTF_CSRF_TIME_LIMIT = 3600       # token válido por 1 hora