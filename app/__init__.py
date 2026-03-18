from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
bcrypt = Bcrypt()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, template_folder='views')
    app.config.from_object('config.Config')

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Debes iniciar sesión para acceder.'
    login_manager.login_message_category = 'warning'

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

    # ── Fecha de hoy disponible en todos los templates ──────────────────────
    from datetime import date

    @app.context_processor
    def inyectar_globals():
        return {'today': date.today().isoformat()}
    
    from flask import redirect, url_for

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    return app
