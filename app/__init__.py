# app/__init__.py — Fábrica de la aplicación Flask (Application Factory Pattern).
# Crea y configura la app, registra extensiones y blueprints.
# Cada blueprint corresponde a un módulo: auth, inventario, movimientos, ventas, productos, reportes.
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect

# Extensiones globales — se inicializan aquí pero se vinculan a la app en create_app()
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
bcrypt = Bcrypt()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, template_folder='views')
    app.config.from_object('config.Config')

    # Inicializar extensiones con la instancia de la app
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    csrf.init_app(app)

    # Redirigir a login si el usuario no está autenticado
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Debes iniciar sesión para acceder.'
    login_manager.login_message_category = 'warning'

    # Registrar blueprints — cada uno agrupa rutas de un módulo funcional
    from app.controllers.auth_controller import auth_bp
    app.register_blueprint(auth_bp)

    from app.controllers.inventario_controller import inventario_bp
    app.register_blueprint(inventario_bp)

    from app.controllers.movimiento_controller import movimiento_bp
    app.register_blueprint(movimiento_bp)

    from app.controllers.venta_controller import venta_bp
    app.register_blueprint(venta_bp)

    from app.controllers.producto_controller import producto_bp
    app.register_blueprint(producto_bp)

    from app.controllers.reporte_controller import reporte_bp
    app.register_blueprint(reporte_bp)

    from app.controllers.campana_controller import campana_bp
    app.register_blueprint(campana_bp)

    from app.controllers.trabajador_controller import trabajador_bp
    app.register_blueprint(trabajador_bp)

    # ── Fecha de hoy disponible en todos los templates ──────────────────────
    from datetime import date

    @app.context_processor
    def inyectar_globals():
        from flask_login import current_user
        from app.models.temporada import Temporada
        campana_activa = None
        if current_user.is_authenticated:
            campana_activa = Temporada.query.filter_by(estado='activa').first()
        return {'today': date.today().isoformat(), 'campana_activa_global': campana_activa}

    from flask import redirect, url_for

    # Ruta raíz: redirige automáticamente al login
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    return app
