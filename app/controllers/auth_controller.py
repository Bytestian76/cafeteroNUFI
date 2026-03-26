# auth_controller.py — Autenticación, dashboard, búsqueda global y gestión de usuarios.
# Rutas: /login, /logout, /dashboard, /dashboard/datos, /buscar,
#         /usuarios, /usuarios/nuevo, /usuarios/editar/<id>,
#         /usuarios/desactivar/<id>, /usuarios/activar/<id>
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from datetime import date, datetime, timedelta
from sqlalchemy import func
from app import db, bcrypt
from app.models.usuario import Usuario
from app.models.inventario import ElementoInventario
from app.models.venta import Venta, DetalleVenta, Cliente
from app.models.movimiento import Movimiento
from app.models.producto import Producto
from app.models.temporada import Temporada
auth_bp = Blueprint('auth', __name__)


# ─── LOGIN ───────────────────────────────────────────────────────────────────
# Soporta petición normal y AJAX (X-Requested-With: XMLHttpRequest).
# En AJAX devuelve JSON; en petición normal redirige o muestra flash.

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']
        es_ajax  = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and not usuario.activo:
            msg = 'Tu cuenta está desactivada. Contacta al administrador.'
            if es_ajax:
                return jsonify({'ok': False, 'mensaje': msg, 'categoria': 'warning'})
            flash(msg, 'warning')
        elif usuario and bcrypt.check_password_hash(usuario.password_hash, password):
            login_user(usuario)
            if es_ajax:
                return jsonify({'ok': True, 'redirect': url_for('auth.dashboard')})
            return redirect(url_for('auth.dashboard'))
        else:
            msg = 'Credenciales incorrectas. Verifica tu correo y contraseña.'
            if es_ajax:
                return jsonify({'ok': False, 'mensaje': msg, 'categoria': 'danger'})
            flash(msg, 'danger')

    return render_template('auth/login.html')


# ─── LOGOUT ──────────────────────────────────────────────────────────────────

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


# ─── DASHBOARD ───────────────────────────────────────────────────────────────
# Calcula KPIs del mes actual y carga las últimas 5 ventas para la tabla.
# Los datos de las gráficas se cargan por AJAX desde /dashboard/datos (línea 100).

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)

    # KPI: total facturado en el mes actual (excluye anuladas)
    total_mes = db.session.query(func.sum(Venta.total)).filter(
        func.date(Venta.fecha) >= inicio_mes,
        Venta.anulada == False
    ).scalar() or 0

    # KPI: número de ventas del mes (excluye anuladas)
    num_ventas_mes = Venta.query.filter(
        func.date(Venta.fecha) >= inicio_mes,
        Venta.anulada == False
    ).count()

    # KPI: clientes registrados
    total_clientes = Cliente.query.count()

    # KPI + alerta: elementos bajo stock mínimo → usa tiene_alerta de inventario.py
    elementos_alerta = ElementoInventario.query.filter(
        ElementoInventario.activo == True,
        ElementoInventario.stock_actual < ElementoInventario.stock_minimo
    ).order_by(ElementoInventario.nombre).all()

    # Tabla: últimas 5 ventas no anuladas → conectado con Venta.cliente (backref en venta.py)
    ultimas_ventas = Venta.query.filter(Venta.anulada == False).order_by(Venta.fecha.desc()).limit(5).all()

    # Campaña activa y últimas dos campañas cerradas → banner y bloque de contraste
    campana_activa  = Temporada.query.filter_by(estado='activa').first()
    cerradas        = Temporada.query.filter_by(estado='cerrada').order_by(Temporada.fecha_fin.desc()).limit(2).all()
    campana_cerrada          = cerradas[0] if len(cerradas) >= 1 else None
    campana_cerrada_anterior = cerradas[1] if len(cerradas) >= 2 else None

    # Bloque de contraste: activa vs última cerrada, o las dos últimas cerradas si no hay activa
    if campana_activa and campana_cerrada:
        contraste_izq = campana_cerrada
        contraste_der = campana_activa
        contraste_der_es_activa = True
    elif campana_cerrada and campana_cerrada_anterior:
        contraste_izq = campana_cerrada_anterior
        contraste_der = campana_cerrada
        contraste_der_es_activa = False
    else:
        contraste_izq = contraste_der = None
        contraste_der_es_activa = False

    return render_template('auth/dashboard.html',
        total_mes=float(total_mes),
        num_ventas_mes=num_ventas_mes,
        total_clientes=total_clientes,
        elementos_alerta=elementos_alerta,
        ultimas_ventas=ultimas_ventas,
        inicio_default=(hoy - timedelta(days=29)).isoformat(),
        fin_default=hoy.isoformat(),
        inicio_mes=inicio_mes.isoformat(),
        campana_activa=campana_activa,
        campana_cerrada=campana_cerrada,
        contraste_izq=contraste_izq,
        contraste_der=contraste_der,
        contraste_der_es_activa=contraste_der_es_activa
    )


# ─── DASHBOARD / DATOS (AJAX para gráficas) ──────────────────────────────────
# Recibe parámetros GET: inicio, fin (YYYY-MM-DD).
# Devuelve JSON con tres series: ventas por día, top productos y movimientos por día.
# Es consumido por el JS en dashboard.html.

@auth_bp.route('/dashboard/datos')
@login_required
def dashboard_datos():
    hoy = date.today()
    inicio_str = request.args.get('inicio', (hoy - timedelta(days=29)).isoformat())
    fin_str    = request.args.get('fin',    hoy.isoformat())

    try:
        inicio = datetime.strptime(inicio_str, '%Y-%m-%d').date()
        fin    = datetime.strptime(fin_str,    '%Y-%m-%d').date()
    except ValueError:
        inicio = hoy - timedelta(days=29)
        fin    = hoy

    # Ventas por día en el rango (excluye anuladas)
    ventas_dia = db.session.query(
        func.date(Venta.fecha).label('dia'),
        func.sum(Venta.total).label('total')
    ).filter(
        func.date(Venta.fecha) >= inicio,
        func.date(Venta.fecha) <= fin,
        Venta.anulada == False
    ).group_by(func.date(Venta.fecha)).order_by('dia').all()

    # Productos por subtotal en el rango, excluye anuladas → conectado con DetalleVenta y Venta
    top_productos = db.session.query(
        Producto.nombre,
        func.sum(DetalleVenta.subtotal).label('total')
    ).join(DetalleVenta, Producto.id == DetalleVenta.producto_id
    ).join(Venta, DetalleVenta.venta_id == Venta.id
    ).filter(
        func.date(Venta.fecha) >= inicio,
        func.date(Venta.fecha) <= fin,
        Venta.anulada == False
    ).group_by(Producto.id, Producto.nombre
    ).order_by(db.desc('total')).all()

    # Movimientos por día, tipo y elemento — incluye nombre para el tooltip
    from collections import defaultdict
    movs_detalle = db.session.query(
        func.date(Movimiento.fecha).label('dia'),
        Movimiento.tipo,
        ElementoInventario.nombre.label('elemento'),
        func.sum(Movimiento.cantidad).label('cantidad')
    ).join(ElementoInventario, Movimiento.elemento_id == ElementoInventario.id
    ).filter(
        func.date(Movimiento.fecha) >= inicio,
        func.date(Movimiento.fecha) <= fin
    ).group_by(func.date(Movimiento.fecha), Movimiento.tipo, ElementoInventario.nombre
    ).order_by('dia').all()

    # Agrupa (fecha, tipo) → {total, elementos[]} para el JSON
    movs_map = defaultdict(lambda: {'total': 0.0, 'elementos': []})
    for r in movs_detalle:
        key = (str(r.dia), r.tipo)
        movs_map[key]['total'] += float(r.cantidad)
        movs_map[key]['elementos'].append(f"{r.elemento} ({float(r.cantidad):g})")

    movimientos_list = [
        {'fecha': k[0], 'tipo': k[1], 'total': round(v['total'], 2), 'elementos': v['elementos']}
        for k, v in sorted(movs_map.items())
    ]

    return jsonify({
        'ventas':        [{'fecha': str(r.dia), 'total': float(r.total)} for r in ventas_dia],
        'top_productos': [{'nombre': r.nombre,  'total': float(r.total)} for r in top_productos],
        'movimientos':   movimientos_list
    })


# ─── BÚSQUEDA GLOBAL ─────────────────────────────────────────────────────────
# Recibe ?q= desde el input del navbar (base.html).
# Busca en paralelo en productos, clientes e inventario con ilike (sin distinción de mayúsculas).

@auth_bp.route('/buscar')
@login_required
def buscar():
    q = request.args.get('q', '').strip()
    resultados = {'productos': [], 'clientes': [], 'inventario': []}

    if q:
        termino = f'%{q}%'
        resultados['productos']  = Producto.query.filter(Producto.nombre.ilike(termino)).limit(8).all()
        resultados['clientes']   = Cliente.query.filter(
            Cliente.nombre.ilike(termino) | Cliente.documento.ilike(termino)
        ).limit(8).all()
        resultados['inventario'] = ElementoInventario.query.filter(
            ElementoInventario.nombre.ilike(termino)
        ).limit(8).all()

    total = sum(len(v) for v in resultados.values())
    return render_template('auth/buscar.html', q=q, resultados=resultados, total=total)


# ─── LISTAR USUARIOS ─────────────────────────────────────────────────────────

@auth_bp.route('/usuarios')
@login_required
def listar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.nombre).all()
    return render_template('auth/usuarios.html', usuarios=usuarios)


# ─── CREAR USUARIO ───────────────────────────────────────────────────────────
# Hashea el password con bcrypt antes de guardarlo → nunca se almacena en texto plano.

@auth_bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_usuario():
    if request.method == 'POST':
        nombre   = request.form['nombre'].strip()
        email    = request.form['email'].strip()
        password = request.form['password']

        if not nombre or not email or not password:
            flash('Todos los campos son obligatorios.', 'danger')
            return render_template('auth/form_usuario.html', usuario=None, form_data=request.form)

        # Verificar que el email no esté en uso
        if Usuario.query.filter_by(email=email).first():
            flash('Ya existe un usuario con ese correo.', 'danger')
            return render_template('auth/form_usuario.html', usuario=None, form_data=request.form)

        hash_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        usuario = Usuario(nombre=nombre, email=email, password_hash=hash_pw)
        db.session.add(usuario)
        db.session.commit()
        flash(f'Usuario {nombre} creado correctamente.', 'success')
        return redirect(url_for('auth.listar_usuarios'))

    return render_template('auth/form_usuario.html', usuario=None)


# ─── EDITAR USUARIO ──────────────────────────────────────────────────────────
# El password solo se actualiza si se envía uno nuevo; si el campo viene vacío, se conserva el actual.

@auth_bp.route('/usuarios/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)

    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        email  = request.form['email'].strip()

        if not nombre or not email:
            flash('Nombre y correo son obligatorios.', 'danger')
            return render_template('auth/form_usuario.html', usuario=usuario, form_data=request.form)

        # Verificar que el email no lo use otro usuario
        existente = Usuario.query.filter_by(email=email).first()
        if existente and existente.id != usuario.id:
            flash('Ese correo ya está en uso por otro usuario.', 'danger')
            return render_template('auth/form_usuario.html', usuario=usuario, form_data=request.form)

        usuario.nombre = nombre
        usuario.email  = email

        # Si se envió nueva contraseña, re-hashearla
        nueva_pw = request.form.get('password', '')
        if nueva_pw:
            usuario.password_hash = bcrypt.generate_password_hash(nueva_pw).decode('utf-8')

        db.session.commit()
        flash(f'Usuario {usuario.nombre} actualizado.', 'success')
        return redirect(url_for('auth.listar_usuarios'))

    return render_template('auth/form_usuario.html', usuario=usuario)


# ─── DESACTIVAR USUARIO ──────────────────────────────────────────────────────
# Pone activo=False. No elimina el registro para conservar historial.
# Un usuario no puede desactivarse a sí mismo.

@auth_bp.route('/usuarios/desactivar/<int:id>', methods=['POST'])
@login_required
def desactivar_usuario(id):
    usuario = Usuario.query.get_or_404(id)

    if usuario.id == current_user.id:
        msg = 'No puedes desactivarte a ti mismo.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'msg': msg, 'categoria': 'warning'})
        flash(msg, 'warning')
        return redirect(url_for('auth.listar_usuarios'))

    usuario.activo = False
    db.session.commit()
    msg = f'Usuario {usuario.nombre} desactivado.'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'msg': msg, 'categoria': 'warning'})
    flash(msg, 'warning')
    return redirect(url_for('auth.listar_usuarios'))


# ─── ACTIVAR USUARIO ─────────────────────────────────────────────────────────

@auth_bp.route('/usuarios/activar/<int:id>', methods=['POST'])
@login_required
def activar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    usuario.activo = True
    db.session.commit()
    msg = f'Usuario {usuario.nombre} activado correctamente.'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'msg': msg, 'categoria': 'success'})
    flash(msg, 'success')
    return redirect(url_for('auth.listar_usuarios'))
