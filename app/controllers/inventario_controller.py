# inventario_controller.py — CRUD de elementos del inventario.
# Rutas: /inventario, /inventario/nuevo, /inventario/editar/<id>,
#         /inventario/desactivar/<id>, /inventario/activar/<id>, /inventario/eliminar/<id>
# La eliminación solo procede si el elemento no tiene movimientos; si los tiene, se desactiva.
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from app import db
from app.models.inventario import ElementoInventario
inventario_bp = Blueprint('inventario', __name__)

POR_PAGINA = 10


# Construye la URL de paginación conservando los filtros activos de categoría e inactivos
def _url_pagina(pagina, categoria='', mostrar_inactivos=''):
    params = f'pagina={pagina}'
    if categoria:
        params += f'&categoria={categoria}'
    if mostrar_inactivos:
        params += f'&inactivos={mostrar_inactivos}'
    return f'/inventario?{params}'


# ─── LISTAR INVENTARIO ────────────────────────────────────────────────────────
# Filtros disponibles: categoría, mostrar inactivos, solo con alerta de escasez.
# La paginación usa el macro paginar() de paginacion.html.

@inventario_bp.route('/inventario')
@login_required
def listar():
    categoria         = request.args.get('categoria', '')
    mostrar_inactivos = request.args.get('inactivos', '')
    solo_alertas      = request.args.get('alerta', '')
    pagina            = request.args.get('pagina', 1, type=int)

    query = ElementoInventario.query
    if not mostrar_inactivos:
        query = query.filter_by(activo=True)
    if categoria:
        query = query.filter_by(categoria=categoria)
    if solo_alertas:
        query = query.filter(ElementoInventario.stock_actual < ElementoInventario.stock_minimo)

    paginacion = query.order_by(ElementoInventario.nombre).paginate(
        page=pagina, per_page=POR_PAGINA, error_out=False
    )

    # Total de inactivos global (independiente de filtros y paginación)
    total_inactivos = ElementoInventario.query.filter_by(activo=False).count()

    url_anterior  = _url_pagina(paginacion.prev_num, categoria, mostrar_inactivos) if paginacion.has_prev else '#'
    url_siguiente = _url_pagina(paginacion.next_num, categoria, mostrar_inactivos) if paginacion.has_next else '#'

    return render_template('inventario/lista.html',
                           elementos=paginacion.items,
                           paginacion=paginacion,
                           categoria=categoria,
                           mostrar_inactivos=mostrar_inactivos,
                           solo_alertas=solo_alertas,
                           total_inactivos=total_inactivos,
                           url_anterior=url_anterior,
                           url_siguiente=url_siguiente)


# ─── NUEVO ELEMENTO ───────────────────────────────────────────────────────────
# Si unidad_medida == 'otro', el valor real viene de unidad_personalizada.
# form_data se pasa al template para repoblar el formulario en caso de error.

@inventario_bp.route('/inventario/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    if request.method == 'POST':
        nombre        = request.form['nombre'].strip()
        categoria     = request.form['categoria']
        stock_actual  = request.form['stock_actual']
        stock_minimo  = request.form['stock_minimo']
        unidad_medida = request.form['unidad_medida']

        if not nombre or not categoria or not unidad_medida:
            flash('Nombre, categoría y unidad de medida son obligatorios.', 'danger')
            return render_template('inventario/form.html', elemento=None, form_data=request.form)

        elemento = ElementoInventario(
            nombre=nombre, categoria=categoria,
            stock_actual=stock_actual, stock_minimo=stock_minimo,
            unidad_medida=unidad_medida
        )
        db.session.add(elemento)
        db.session.commit()
        flash(f'Elemento "{nombre}" registrado correctamente.', 'success')
        return redirect(url_for('inventario.listar'))

    return render_template('inventario/form.html', elemento=None)


# ─── EDITAR ELEMENTO ──────────────────────────────────────────────────────────

@inventario_bp.route('/inventario/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    elemento = ElementoInventario.query.get_or_404(id)

    if request.method == 'POST':
        elemento.nombre        = request.form['nombre'].strip()
        elemento.categoria     = request.form['categoria']
        elemento.stock_actual  = request.form['stock_actual']
        elemento.stock_minimo  = request.form['stock_minimo']
        elemento.unidad_medida = request.form['unidad_medida']

        db.session.commit()
        flash(f'Elemento "{elemento.nombre}" actualizado.', 'success')
        return redirect(url_for('inventario.listar'))

    return render_template('inventario/form.html', elemento=elemento)


# ─── DESACTIVAR ELEMENTO ──────────────────────────────────────────────────────
# Pone activo=False. Deja de aparecer en listados y movimientos, pero conserva historial.

@inventario_bp.route('/inventario/desactivar/<int:id>', methods=['POST'])
@login_required
def desactivar(id):
    elemento = ElementoInventario.query.get_or_404(id)
    elemento.activo = False
    db.session.commit()
    msg = f'Elemento "{elemento.nombre}" desactivado. Ya no emitirá alertas.'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'msg': msg, 'categoria': 'warning', 'tiene_alerta': False})
    flash(msg, 'warning')
    return redirect(url_for('inventario.listar'))


# ─── ACTIVAR ELEMENTO ────────────────────────────────────────────────────────

@inventario_bp.route('/inventario/activar/<int:id>', methods=['POST'])
@login_required
def activar(id):
    elemento = ElementoInventario.query.get_or_404(id)
    elemento.activo = True
    db.session.commit()
    msg = f'Elemento "{elemento.nombre}" activado correctamente.'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'msg': msg, 'categoria': 'success', 'tiene_alerta': elemento.tiene_alerta})
    flash(msg, 'success')
    return redirect(url_for('inventario.listar'))


# ─── ELIMINAR ELEMENTO ───────────────────────────────────────────────────────
# Eliminar es permanente. Si tiene movimientos registrados se bloquea la eliminación
# y se sugiere desactivar en su lugar (para preservar el historial de movimientos).

@inventario_bp.route('/inventario/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar(id):
    elemento = ElementoInventario.query.get_or_404(id)

    # Verificar si tiene movimientos asociados → relación definida en inventario.py
    if elemento.movimientos:
        msg = f'No se puede eliminar "{elemento.nombre}" porque tiene {len(elemento.movimientos)} movimiento(s) registrado(s). Desactívalo en su lugar.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'msg': msg, 'categoria': 'danger'})
        flash(msg, 'danger')
        return redirect(url_for('inventario.listar'))

    nombre = elemento.nombre
    db.session.delete(elemento)
    db.session.commit()
    msg = f'Elemento "{nombre}" eliminado permanentemente.'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'msg': msg, 'categoria': 'danger'})
    flash(msg, 'danger')
    return redirect(url_for('inventario.listar'))
