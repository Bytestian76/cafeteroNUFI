from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from app.models.usuario import Usuario
from app.models.inventario import ElementoInventario
from app.utils.decorators import rol_requerido

auth_bp = Blueprint('auth', __name__)


# ─── LOGIN ───────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and not usuario.activo:
            flash('Tu cuenta está desactivada. Contacta al administrador.', 'warning')
        elif usuario and bcrypt.check_password_hash(usuario.password_hash, password):
            login_user(usuario)
            return redirect(url_for('auth.dashboard'))
        else:
            flash('Credenciales incorrectas.', 'danger')

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
    # Filtra directamente en SQL — más eficiente que cargar todo en Python
    elementos_alerta = ElementoInventario.query.filter(
        ElementoInventario.activo == True,
        ElementoInventario.stock_actual < ElementoInventario.stock_minimo
    ).order_by(ElementoInventario.nombre).all()

    return render_template('auth/dashboard.html', elementos_alerta=elementos_alerta)


# ─── LISTAR USUARIOS ─────────────────────────────────────────────────────────

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
        nombre   = request.form['nombre'].strip()
        email    = request.form['email'].strip()
        password = request.form['password']
        rol      = request.form.get('rol', 'admin')

        if not nombre or not email or not password:
            flash('Todos los campos son obligatorios.', 'danger')
            return render_template('auth/form_usuario.html', usuario=None)

        if Usuario.query.filter_by(email=email).first():
            flash('Ya existe un usuario con ese correo.', 'danger')
            return render_template('auth/form_usuario.html', usuario=None)

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
        nombre = request.form['nombre'].strip()
        email  = request.form['email'].strip()

        if not nombre or not email:
            flash('Nombre y correo son obligatorios.', 'danger')
            return render_template('auth/form_usuario.html', usuario=usuario)

        # Verificar que el email no lo use otro usuario
        existente = Usuario.query.filter_by(email=email).first()
        if existente and existente.id != usuario.id:
            flash('Ese correo ya está en uso por otro usuario.', 'danger')
            return render_template('auth/form_usuario.html', usuario=usuario)

        usuario.nombre = nombre
        usuario.email  = email
        usuario.rol    = request.form.get('rol', 'admin')

        nueva_pw = request.form.get('password', '')
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


# ─── ACTIVAR USUARIO ─────────────────────────────────────────────────────────

@auth_bp.route('/usuarios/activar/<int:id>', methods=['POST'])
@login_required
@rol_requerido('admin')
def activar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    usuario.activo = True
    db.session.commit()
    flash(f'Usuario {usuario.nombre} activado correctamente.', 'success')
    return redirect(url_for('auth.listar_usuarios'))
