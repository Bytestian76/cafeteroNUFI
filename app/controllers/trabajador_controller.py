# trabajador_controller.py — Gestión de trabajadores y registro de jornales.
# Rutas: /trabajadores (lista), /trabajadores/nuevo, /trabajadores/<id>/editar,
#         /trabajadores/<id> (detalle), /jornales/nuevo, /jornales/<id>/eliminar,
#         /operaciones (hub de selección)
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.trabajador import Trabajador
from app.models.jornal import Jornal
from app.models.temporada import Temporada
from datetime import date

trabajador_bp = Blueprint('trabajadores', __name__)


# ─── HUB OPERACIONES ──────────────────────────────────────────────────────────

@trabajador_bp.route('/operaciones')
@login_required
def hub_operaciones():
    from app.models.temporada import Temporada
    activa = Temporada.query.filter_by(estado='activa').first()
    return render_template('operaciones/hub.html', campana_activa_global=activa)


# ─── LISTAR TRABAJADORES ──────────────────────────────────────────────────────

@trabajador_bp.route('/trabajadores')
@login_required
def listar():
    trabajadores = Trabajador.query.order_by(Trabajador.activo.desc(), Trabajador.nombre).all()
    return render_template('trabajadores/lista.html', trabajadores=trabajadores)


# ─── CREAR TRABAJADOR ─────────────────────────────────────────────────────────

@trabajador_bp.route('/trabajadores/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    if request.method == 'POST':
        nombre    = request.form.get('nombre', '').strip()
        documento = request.form.get('documento', '').strip() or None
        telefono  = request.form.get('telefono', '').strip() or None

        if not nombre:
            flash('El nombre es obligatorio.', 'danger')
            return render_template('trabajadores/form.html', trabajador=None)

        trabajador = Trabajador(nombre=nombre, documento=documento, telefono=telefono)
        db.session.add(trabajador)
        db.session.commit()
        flash(f'Trabajador "{nombre}" registrado correctamente.', 'success')
        return redirect(url_for('trabajadores.listar'))

    return render_template('trabajadores/form.html', trabajador=None)


# ─── EDITAR TRABAJADOR ────────────────────────────────────────────────────────

@trabajador_bp.route('/trabajadores/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    trabajador = Trabajador.query.get_or_404(id)

    if request.method == 'POST':
        nombre    = request.form.get('nombre', '').strip()
        documento = request.form.get('documento', '').strip() or None
        telefono  = request.form.get('telefono', '').strip() or None
        activo    = request.form.get('activo') == '1'

        if not nombre:
            flash('El nombre es obligatorio.', 'danger')
            return render_template('trabajadores/form.html', trabajador=trabajador)

        trabajador.nombre    = nombre
        trabajador.documento = documento
        trabajador.telefono  = telefono
        trabajador.activo    = activo
        db.session.commit()
        flash(f'Trabajador "{nombre}" actualizado.', 'success')
        return redirect(url_for('trabajadores.detalle', id=id))

    return render_template('trabajadores/form.html', trabajador=trabajador)


# ─── DETALLE TRABAJADOR ───────────────────────────────────────────────────────
# Muestra historial de jornales con filtros y agrupado por temporada.

@trabajador_bp.route('/trabajadores/<int:id>')
@login_required
def detalle(id):
    from collections import defaultdict
    trabajador = Trabajador.query.get_or_404(id)

    # Filtros desde query params
    temporada_id = request.args.get('temporada_id', type=int)
    fecha_desde  = request.args.get('fecha_desde', '').strip() or None
    fecha_hasta  = request.args.get('fecha_hasta', '').strip() or None

    query = Jornal.query.filter_by(trabajador_id=id)
    if temporada_id:
        query = query.filter_by(campana_id=temporada_id)
    if fecha_desde:
        try:
            query = query.filter(Jornal.fecha >= date.fromisoformat(fecha_desde))
        except ValueError:
            fecha_desde = None
    if fecha_hasta:
        try:
            query = query.filter(Jornal.fecha <= date.fromisoformat(fecha_hasta))
        except ValueError:
            fecha_hasta = None

    jornales     = query.order_by(Jornal.fecha.desc()).all()
    total_pagado = float(sum(j.total for j in jornales))

    # Agrupar por temporada (más reciente primero según fecha_inicio)
    temp_map    = {j.campana_id: j.campana for j in jornales}
    temp_groups = defaultdict(list)
    for j in jornales:
        temp_groups[j.campana_id].append(j)

    grupos = []
    for tid in sorted(temp_map, key=lambda x: temp_map[x].fecha_inicio, reverse=True):
        t = temp_map[tid]
        grupo_jornales = sorted(temp_groups[tid], key=lambda x: x.fecha, reverse=True)
        grupos.append({
            'temporada': t,
            'jornales':  grupo_jornales,
            'subtotal':  float(sum(j.total for j in grupo_jornales)),
        })

    # Temporadas donde este trabajador tiene jornales (para el select del filtro)
    tids = db.session.query(Jornal.campana_id).filter_by(trabajador_id=id).distinct().all()
    temporadas = Temporada.query.filter(
        Temporada.id.in_([t[0] for t in tids])
    ).order_by(Temporada.fecha_inicio.desc()).all()

    filtros = dict(temporada_id=temporada_id, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)

    return render_template('trabajadores/detalle.html',
                           trabajador=trabajador,
                           jornales=jornales,
                           total_pagado=total_pagado,
                           grupos=grupos,
                           temporadas=temporadas,
                           filtros=filtros)


# ─── NUEVO JORNAL ─────────────────────────────────────────────────────────────
# campana_id se pasa como query param desde el detalle de la temporada.

@trabajador_bp.route('/jornales/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_jornal():
    campanas_activas = Temporada.query.filter_by(estado='activa').all()
    trabajadores_activos = Trabajador.query.filter_by(activo=True).order_by(Trabajador.nombre).all()
    campana_id_pre = request.args.get('campana_id', type=int)

    if request.method == 'POST':
        trabajador_id     = request.form.get('trabajador_id', type=int)
        campana_id        = request.form.get('campana_id', type=int)
        fecha_str         = request.form.get('fecha')
        cantidad_jornales = request.form.get('cantidad_jornales', '').strip()
        valor_jornal      = request.form.get('valor_jornal', '').strip()
        observacion       = request.form.get('observacion', '').strip() or None

        errores = []
        if not trabajador_id:   errores.append('Selecciona un trabajador.')
        if not campana_id:      errores.append('Selecciona una temporada.')
        if not fecha_str:       errores.append('La fecha es obligatoria.')
        if not cantidad_jornales: errores.append('La cantidad de jornales es obligatoria.')
        if not valor_jornal:    errores.append('El valor por jornal es obligatorio.')

        if errores:
            for e in errores:
                flash(e, 'danger')
            return render_template('trabajadores/form_jornal.html',
                                   trabajadores=trabajadores_activos,
                                   campanas=campanas_activas,
                                   campana_id_pre=campana_id)

        try:
            fecha     = date.fromisoformat(fecha_str)
            cantidad  = float(cantidad_jornales)
            valor     = float(valor_jornal)
            total     = round(cantidad * valor, 2)
        except (ValueError, TypeError):
            flash('Datos numéricos o de fecha inválidos.', 'danger')
            return render_template('trabajadores/form_jornal.html',
                                   trabajadores=trabajadores_activos,
                                   campanas=campanas_activas,
                                   campana_id_pre=campana_id)

        jornal = Jornal(
            trabajador_id=trabajador_id,
            campana_id=campana_id,
            fecha=fecha,
            cantidad_jornales=cantidad,
            valor_jornal=valor,
            total=total,
            observacion=observacion,
            usuario_id=current_user.id
        )
        db.session.add(jornal)
        db.session.commit()
        flash('Jornal registrado correctamente.', 'success')
        return redirect(url_for('campanas.detalle', id=campana_id))

    return render_template('trabajadores/form_jornal.html',
                           trabajadores=trabajadores_activos,
                           campanas=campanas_activas,
                           campana_id_pre=campana_id_pre)


# ─── ELIMINAR JORNAL ──────────────────────────────────────────────────────────

@trabajador_bp.route('/jornales/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_jornal(id):
    jornal = Jornal.query.get_or_404(id)
    campana_id = jornal.campana_id
    db.session.delete(jornal)
    db.session.commit()
    flash('Jornal eliminado.', 'success')
    return redirect(url_for('campanas.detalle', id=campana_id))
