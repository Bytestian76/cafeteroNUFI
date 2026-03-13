from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.movimiento import Movimiento
from app.models.inventario import ElementoInventario
from app.utils.decorators import rol_requerido
from datetime import datetime, timedelta

movimiento_bp = Blueprint('movimientos', __name__)

POR_PAGINA = 15


def _url_pagina(pagina, elemento_id='', tipo='', fecha_desde='', fecha_hasta=''):
    """Construye la URL de paginación conservando los filtros activos."""
    params = f'pagina={pagina}'
    if elemento_id:
        params += f'&elemento_id={elemento_id}'
    if tipo:
        params += f'&tipo={tipo}'
    if fecha_desde:
        params += f'&fecha_desde={fecha_desde}'
    if fecha_hasta:
        params += f'&fecha_hasta={fecha_hasta}'
    return f'/movimientos?{params}'


# ─── HISTORIAL DE MOVIMIENTOS ─────────────────────────────────────────────────

@movimiento_bp.route('/movimientos')
@login_required
def historial():
    elemento_id = request.args.get('elemento_id', '')
    tipo        = request.args.get('tipo', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')
    pagina      = request.args.get('pagina', 1, type=int)

    query = Movimiento.query

    if elemento_id:
        query = query.filter_by(elemento_id=elemento_id)
    if tipo:
        query = query.filter_by(tipo=tipo)

    if fecha_desde:
        try:
            dt_desde = datetime.strptime(fecha_desde, '%Y-%m-%d')
            query = query.filter(Movimiento.fecha >= dt_desde)
        except ValueError:
            pass

    if fecha_hasta:
        try:
            dt_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            query = query.filter(Movimiento.fecha <= dt_hasta)
        except ValueError:
            pass

    paginacion = query.order_by(Movimiento.fecha.desc()).paginate(
        page=pagina, per_page=POR_PAGINA, error_out=False
    )
    elementos = ElementoInventario.query.filter_by(activo=True).order_by(ElementoInventario.nombre).all()

    url_anterior  = _url_pagina(paginacion.prev_num, elemento_id, tipo, fecha_desde, fecha_hasta) if paginacion.has_prev else '#'
    url_siguiente = _url_pagina(paginacion.next_num, elemento_id, tipo, fecha_desde, fecha_hasta) if paginacion.has_next else '#'

    return render_template('movimientos/historial.html',
                           movimientos=paginacion.items,
                           paginacion=paginacion,
                           elementos=elementos,
                           url_anterior=url_anterior,
                           url_siguiente=url_siguiente,
                           filtros={'elemento_id': elemento_id, 'tipo': tipo,
                                    'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta})


# ─── REGISTRAR MOVIMIENTO ─────────────────────────────────────────────────────

@movimiento_bp.route('/movimientos/nuevo', methods=['GET', 'POST'])
@login_required
@rol_requerido('admin')
def nuevo():
    elementos = ElementoInventario.query.filter_by(activo=True).order_by(ElementoInventario.nombre).all()

    if request.method == 'POST':
        elemento_id = int(request.form['elemento_id'])
        tipo        = request.form['tipo']
        cantidad    = float(request.form['cantidad'])
        observacion = request.form.get('observacion', '')

        elemento = ElementoInventario.query.get_or_404(elemento_id)

        if tipo == 'salida' and cantidad > float(elemento.stock_actual):
            flash(f'Stock insuficiente. Stock actual: {elemento.stock_actual} {elemento.unidad_medida}.', 'danger')
            return render_template('movimientos/nuevo.html', elementos=elementos)

        if tipo == 'entrada':
            elemento.stock_actual = float(elemento.stock_actual) + cantidad
        else:
            elemento.stock_actual = float(elemento.stock_actual) - cantidad

        movimiento = Movimiento(
            elemento_id=elemento_id,
            tipo=tipo,
            cantidad=cantidad,
            observacion=observacion,
            usuario_id=current_user.id
        )
        db.session.add(movimiento)
        db.session.commit()

        if elemento.tiene_alerta():
            flash(f'⚠️ Alerta: "{elemento.nombre}" está por debajo del stock mínimo ({elemento.stock_minimo} {elemento.unidad_medida}).', 'warning')

        flash(f'Movimiento de {tipo} registrado correctamente.', 'success')
        return redirect(url_for('movimientos.historial'))

    return render_template('movimientos/nuevo.html', elementos=elementos)
