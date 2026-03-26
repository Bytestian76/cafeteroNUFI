# producto_controller.py — CRUD del catálogo de productos vendibles.
# Rutas: /productos, /productos/nuevo, /productos/editar/<id>,
#         /productos/desactivar/<id>, /productos/activar/<id>
# Los productos inactivos no aparecen en el formulario de nueva factura.
# El stock_actual se descuenta/restaura desde venta_controller.py al facturar/anular.
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from app import db
from app.models.producto import Producto
producto_bp = Blueprint('productos', __name__)

POR_PAGINA = 10


# Construye URL de paginación conservando filtros de nombre y estado
def _url_pagina(pagina, nombre='', estado=''):
    params = f'pagina={pagina}'
    if nombre:
        params += f'&nombre={nombre}'
    if estado:
        params += f'&estado={estado}'
    return f'/productos?{params}'


# ─── LISTAR PRODUCTOS ─────────────────────────────────────────────────────────
# Filtros: nombre (búsqueda parcial ilike) y estado (activo/inactivo/todos).
# KPIs globales: total sin stock y total inactivos (sin aplicar filtros actuales).

@producto_bp.route('/productos')
@login_required
def listar():
    nombre_filtro = request.args.get('nombre', '').strip()
    estado_filtro = request.args.get('estado', '')   # 'activo', 'inactivo', '' = todos
    pagina        = request.args.get('pagina', 1, type=int)

    query = Producto.query

    if nombre_filtro:
        query = query.filter(Producto.nombre.ilike(f'%{nombre_filtro}%'))

    if estado_filtro == 'activo':
        query = query.filter_by(activo=True)
    elif estado_filtro == 'inactivo':
        query = query.filter_by(activo=False)

    paginacion = query.order_by(Producto.nombre).paginate(
        page=pagina, per_page=POR_PAGINA, error_out=False
    )

    url_anterior  = _url_pagina(paginacion.prev_num, nombre_filtro, estado_filtro) if paginacion.has_prev else '#'
    url_siguiente = _url_pagina(paginacion.next_num, nombre_filtro, estado_filtro) if paginacion.has_next else '#'

    # Conteos globales para KPIs (sin los filtros de búsqueda actuales)
    total_sin_stock = Producto.query.filter_by(activo=True).filter(Producto.stock_actual <= 0).count()
    total_inactivos = Producto.query.filter_by(activo=False).count()

    return render_template('productos/lista.html',
                           productos=paginacion.items,
                           paginacion=paginacion,
                           filtros={'nombre': nombre_filtro, 'estado': estado_filtro},
                           url_anterior=url_anterior,
                           url_siguiente=url_siguiente,
                           total_sin_stock=total_sin_stock,
                           total_inactivos=total_inactivos)


# ─── NUEVO PRODUCTO ───────────────────────────────────────────────────────────
# Si unidad_medida == 'otro', toma el valor de unidad_personalizada en su lugar.

@producto_bp.route('/productos/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    if request.method == 'POST':
        nombre          = request.form['nombre'].strip()
        descripcion     = request.form.get('descripcion', '').strip()
        precio_unitario = request.form['precio_unitario']
        unidad_sel      = request.form.get('unidad_medida', '').strip()
        # Si eligió 'otro', usar el texto libre del campo personalizado
        unidad_medida   = request.form.get('unidad_personalizada', '').strip() if unidad_sel == 'otro' else unidad_sel
        stock_actual    = request.form.get('stock_actual', '0')

        if not nombre or not precio_unitario or not unidad_medida:
            flash('Nombre, precio y unidad de medida son obligatorios.', 'danger')
            return render_template('productos/form.html', producto=None, form_data=request.form)

        if float(precio_unitario) < 0:
            flash('El precio no puede ser negativo.', 'danger')
            return render_template('productos/form.html', producto=None, form_data=request.form)

        producto = Producto(
            nombre=nombre,
            descripcion=descripcion,
            precio_unitario=precio_unitario,
            unidad_medida=unidad_medida,
            stock_actual=float(stock_actual)
        )
        db.session.add(producto)
        db.session.commit()
        flash(f'Producto "{nombre}" registrado correctamente.', 'success')
        return redirect(url_for('productos.listar'))

    return render_template('productos/form.html', producto=None)


# ─── EDITAR PRODUCTO ──────────────────────────────────────────────────────────
# Misma lógica de unidad_personalizada que en nuevo().

@producto_bp.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    producto = Producto.query.get_or_404(id)

    if request.method == 'POST':
        nombre          = request.form['nombre'].strip()
        descripcion     = request.form.get('descripcion', '').strip()
        precio_unitario = request.form['precio_unitario']
        unidad_sel      = request.form.get('unidad_medida', '').strip()
        unidad_medida   = request.form.get('unidad_personalizada', '').strip() if unidad_sel == 'otro' else unidad_sel
        stock_actual    = request.form.get('stock_actual', '0')

        if not nombre or not precio_unitario or not unidad_medida:
            flash('Nombre, precio y unidad de medida son obligatorios.', 'danger')
            return render_template('productos/form.html', producto=producto, form_data=request.form)

        if float(precio_unitario) < 0:
            flash('El precio no puede ser negativo.', 'danger')
            return render_template('productos/form.html', producto=producto, form_data=request.form)

        producto.nombre          = nombre
        producto.descripcion     = descripcion
        producto.precio_unitario = precio_unitario
        producto.unidad_medida   = unidad_medida
        producto.stock_actual    = float(stock_actual)

        db.session.commit()
        flash(f'Producto "{producto.nombre}" actualizado.', 'success')
        return redirect(url_for('productos.listar'))

    return render_template('productos/form.html', producto=producto)


# ─── AGREGAR STOCK ────────────────────────────────────────────────────────────
# Suma una cantidad al stock_actual del producto → llamado desde lista.html modal "+ Stock"

@producto_bp.route('/productos/agregar-stock/<int:id>', methods=['POST'])
@login_required
def agregar_stock(id):
    producto = Producto.query.get_or_404(id)
    try:
        cantidad = float(request.form.get('cantidad', 0))
    except ValueError:
        cantidad = 0

    if cantidad <= 0:
        msg = 'La cantidad debe ser mayor a cero.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'msg': msg, 'categoria': 'danger'})
        flash(msg, 'danger')
        return redirect(url_for('productos.listar'))

    producto.stock_actual = float(producto.stock_actual or 0) + cantidad
    db.session.commit()
    nuevo_stock = producto.stock_actual
    msg = f'Se agregaron {cantidad:g} {producto.unidad_medida} al stock de "{producto.nombre}".'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'msg': msg, 'categoria': 'success', 'nuevo_stock': nuevo_stock})
    flash(msg, 'success')
    return redirect(url_for('productos.listar'))


# ─── DESACTIVAR PRODUCTO ──────────────────────────────────────────────────────
# Un producto inactivo deja de aparecer en nueva factura y en filtros de ventas.

@producto_bp.route('/productos/desactivar/<int:id>', methods=['POST'])
@login_required
def desactivar(id):
    producto = Producto.query.get_or_404(id)
    producto.activo = False
    db.session.commit()
    msg = f'Producto "{producto.nombre}" desactivado.'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'msg': msg, 'categoria': 'warning'})
    flash(msg, 'warning')
    return redirect(url_for('productos.listar'))


# ─── ACTIVAR PRODUCTO ─────────────────────────────────────────────────────────

@producto_bp.route('/productos/activar/<int:id>', methods=['POST'])
@login_required
def activar(id):
    producto = Producto.query.get_or_404(id)
    producto.activo = True
    db.session.commit()
    msg = f'Producto "{producto.nombre}" activado correctamente.'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'msg': msg, 'categoria': 'success'})
    flash(msg, 'success')
    return redirect(url_for('productos.listar'))
