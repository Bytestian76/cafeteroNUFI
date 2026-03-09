from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from app.models.usuario import Usuario
from app.models.inventario import ElementoInventario
from app.utils.decorators import rol_requerido

auth_bp = Blueprint('auth', __name__)
@auth_bp.route('/')
def index():
    return redirect(url_for('auth.login'))


# ─── LOGIN ───────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']
        usuario  = Usuario.query.filter_by(email=email, activo=True).first()

        if usuario and bcrypt.check_password_hash(usuario.password_hash, password):
            login_user(usuario)
            return redirect(url_for('auth.dashboard'))
        flash('Credenciales incorrectas', 'danger')

    return render_template('auth/login.html')


# ─── LOGOUT ──────────────────────────────────────────────────────────────────

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    # Consultar elementos con alerta de escasez para mostrar en el dashboard
    elementos_alerta = [
        e for e in ElementoInventario.query.filter_by(activo=True).all()
        if e.tiene_alerta()
    ]
    return render_template('auth/dashboard.html', elementos_alerta=elementos_alerta)


# ─── LISTAR USUARIOS (solo admin) ────────────────────────────────────────────

@auth_bp.route('/usuarios')
@login_required
@rol_requerido('admin')
def listar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.nombre).all()
    return render_template('auth/usuarios.html', usuarios=usuarios)


# ─── CREAR USUARIO ───────────────────────────────────────────────────────────

@auth_bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@login_required
@rol_requerido('admin')
def nuevo_usuario():
    if request.method == 'POST':
        nombre   = request.form['nombre']
        email    = request.form['email']
        password = request.form['password']
        rol      = request.form['rol']

        if Usuario.query.filter_by(email=email).first():
            flash('Ya existe un usuario con ese correo.', 'danger')
            return redirect(url_for('auth.nuevo_usuario'))

        hash_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        usuario = Usuario(nombre=nombre, email=email, password_hash=hash_pw, rol=rol)
        db.session.add(usuario)
        db.session.commit()
        flash(f'Usuario {nombre} creado correctamente.', 'success')
        return redirect(url_for('auth.listar_usuarios'))

    return render_template('auth/form_usuario.html', usuario=None)


# ─── EDITAR USUARIO ──────────────────────────────────────────────────────────

@auth_bp.route('/usuarios/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@rol_requerido('admin')
def editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)

    if request.method == 'POST':
        usuario.nombre = request.form['nombre']
        usuario.email  = request.form['email']
        usuario.rol    = request.form['rol']

        nueva_pw = request.form['password']
        if nueva_pw:
            usuario.password_hash = bcrypt.generate_password_hash(nueva_pw).decode('utf-8')

        db.session.commit()
        flash(f'Usuario {usuario.nombre} actualizado.', 'success')
        return redirect(url_for('auth.listar_usuarios'))

    return render_template('auth/form_usuario.html', usuario=usuario)


# ─── DESACTIVAR USUARIO ──────────────────────────────────────────────────────

@auth_bp.route('/usuarios/desactivar/<int:id>', methods=['POST'])
@login_required
@rol_requerido('admin')
def desactivar_usuario(id):
    usuario = Usuario.query.get_or_404(id)

    if usuario.id == current_user.id:
        flash('No puedes desactivarte a ti mismo.', 'warning')
        return redirect(url_for('auth.listar_usuarios'))

    usuario.activo = False
    db.session.commit()
    flash(f'Usuario {usuario.nombre} desactivado.', 'warning')
    return redirect(url_for('auth.listar_usuarios'))