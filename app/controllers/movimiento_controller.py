# movimiento_controller.py — Registro y consulta de entradas/salidas de inventario.
# Rutas: /movimientos (historial con filtros), /movimientos/nuevo.
# Al registrar un movimiento actualiza directamente ElementoInventario.stock_actual.
# Si tras la salida el stock queda bajo el mínimo, emite alerta flash.
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.movimiento import Movimiento
from app.models.inventario import ElementoInventario
from app.models.temporada import Temporada
from datetime import datetime, timedelta

movimiento_bp = Blueprint('movimientos', __name__)

POR_PAGINA = 10


def _url_pagina(pagina, elemento_id='', tipo='', fecha_desde='', fecha_hasta='', campana_id=''):
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
    if campana_id:
        params += f'&campana_id={campana_id}'
    return f'/movimientos?{params}'


# ─── HISTORIAL DE MOVIMIENTOS ─────────────────────────────────────────────────
# Filtros: por elemento, tipo (entrada/salida) y rango de fechas.
# fecha_hasta se extiende hasta las 23:59:59 del día seleccionado para incluir todo el día.

@movimiento_bp.route('/movimientos')
@login_required
def historial():
    elemento_id = request.args.get('elemento_id', '')
    tipo        = request.args.get('tipo', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')
    campana_id  = request.args.get('campana_id', '')
    pagina      = request.args.get('pagina', 1, type=int)

    query = Movimiento.query

    if elemento_id:
        query = query.filter_by(elemento_id=elemento_id)
    if tipo:
        query = query.filter_by(tipo=tipo)
    if campana_id:
        query = query.filter_by(campana_id=campana_id)

    if fecha_desde:
        try:
            dt_desde = datetime.strptime(fecha_desde, '%Y-%m-%d')
            query = query.filter(Movimiento.fecha >= dt_desde)
        except ValueError:
            pass

    if fecha_hasta:
        try:
            # Extender hasta el último segundo del día para incluir todo el día
            dt_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            query = query.filter(Movimiento.fecha <= dt_hasta)
        except ValueError:
            pass

    # KPIs de conteo y valor económico sobre la query filtrada (antes de paginar)
    from sqlalchemy import func
    total_entradas      = query.filter(Movimiento.tipo == 'entrada').count()
    total_salidas       = query.filter(Movimiento.tipo == 'salida').count()
    total_valor_entradas = float(query.filter(Movimiento.tipo == 'entrada').with_entities(func.sum(Movimiento.valor)).scalar() or 0)
    total_valor_salidas  = float(query.filter(Movimiento.tipo == 'salida').with_entities(func.sum(Movimiento.valor)).scalar() or 0)

    paginacion = query.order_by(Movimiento.fecha.desc()).paginate(
        page=pagina, per_page=POR_PAGINA, error_out=False
    )
    # Solo elementos activos en el select de filtro
    elementos = ElementoInventario.query.filter_by(activo=True).order_by(ElementoInventario.nombre).all()
    campanas  = Temporada.query.order_by(Temporada.fecha_inicio.desc()).all()

    url_anterior  = _url_pagina(paginacion.prev_num, elemento_id, tipo, fecha_desde, fecha_hasta, campana_id) if paginacion.has_prev else '#'
    url_siguiente = _url_pagina(paginacion.next_num, elemento_id, tipo, fecha_desde, fecha_hasta, campana_id) if paginacion.has_next else '#'

    return render_template('movimientos/historial.html',
                        movimientos=paginacion.items,
                        paginacion=paginacion,
                        elementos=elementos,
                        campanas=campanas,
                        url_anterior=url_anterior,
                        url_siguiente=url_siguiente,
                        total_entradas=total_entradas,
                        total_salidas=total_salidas,
                        total_valor_entradas=total_valor_entradas,
                        total_valor_salidas=total_valor_salidas,
                        today=datetime.today().strftime('%Y-%m-%d'),
                        filtros={'elemento_id': elemento_id, 'tipo': tipo,
                                    'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta,
                                    'campana_id': campana_id})


# ─── REGISTRAR MOVIMIENTO ─────────────────────────────────────────────────────
# Valida que no haya salida mayor al stock disponible antes de guardar.
# Actualiza stock_actual del elemento → modelo ElementoInventario en inventario.py.
# Tras guardar verifica tiene_alerta (inventario.py) para emitir alerta si stock quedó bajo.

@movimiento_bp.route('/movimientos/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    elementos       = ElementoInventario.query.filter_by(activo=True).order_by(ElementoInventario.nombre).all()
    campana_activa  = Temporada.query.filter_by(estado='activa').first()

    if request.method == 'POST':
        elemento_id = int(request.form['elemento_id'])
        tipo        = request.form['tipo']
        cantidad    = float(request.form['cantidad'])
        valor       = float(request.form.get('valor', 0) or 0)
        observacion = request.form.get('observacion', '')
        # campana_id solo se guarda si el usuario marcó la casilla de asociar
        campana_id  = request.form.get('campana_id') or None

        elemento = ElementoInventario.query.get_or_404(elemento_id)

        # Bloquear salida si no hay stock suficiente
        if tipo == 'salida' and cantidad > float(elemento.stock_actual):
            flash(f'Stock insuficiente. Stock actual: {elemento.stock_actual} {elemento.unidad_medida}.', 'danger')
            return render_template('movimientos/nuevo.html', elementos=elementos, campana_activa=campana_activa)

        # Actualizar stock del elemento según el tipo de movimiento
        if tipo == 'entrada':
            elemento.stock_actual = float(elemento.stock_actual) + cantidad
        else:
            elemento.stock_actual = float(elemento.stock_actual) - cantidad

        movimiento = Movimiento(
            elemento_id=elemento_id,
            tipo=tipo,
            cantidad=cantidad,
            valor=valor,
            observacion=observacion,
            usuario_id=current_user.id,
            campana_id=campana_id
        )
        db.session.add(movimiento)
        db.session.commit()

        # Alerta si el stock quedó por debajo del mínimo → tiene_alerta en inventario.py
        if elemento.tiene_alerta:
            flash(f'⚠️ Alerta: "{elemento.nombre}" está por debajo del stock mínimo ({elemento.stock_minimo} {elemento.unidad_medida}).', 'warning')

        flash(f'Movimiento de {tipo} registrado correctamente.', 'success')
        return redirect(url_for('movimientos.historial'))

    return render_template('movimientos/nuevo.html', elementos=elementos, campana_activa=campana_activa)
