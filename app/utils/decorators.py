from functools import wraps
from flask import abort
from flask_login import current_user

def rol_requerido(*roles):
    """Solo se usa para proteger rutas que requieren rol admin."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.rol not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator
