from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models.producto import Producto
from app.utils.decorators import rol_requerido

producto_bp = Blueprint('productos', __name__)

POR_PAGINA = 10


def _url_pagina(pagina, nombre='', estado=''):
    params = f'pagina={pagina}'
    if nombre:
        params += f'&nombre={nombre}'
    if estado:
        params += f'&estado={estado}'
    return f'/productos?{params}'


# ─── LISTAR PRODUCTOS ─────────────────────────────────────────────────────────

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

    return render_template('productos/lista.html',
                           productos=paginacion.items,
                           paginacion=paginacion,
                           filtros={'nombre': nombre_filtro, 'estado': estado_filtro},
                           url_anterior=url_anterior,
                           url_siguiente=url_siguiente)


# ─── NUEVO PRODUCTO ───────────────────────────────────────────────────────────

@producto_bp.route('/productos/nuevo', methods=['GET', 'POST'])
@login_required
@rol_requerido('admin')
def nuevo():
    if request.method == 'POST':
        nombre          = request.form['nombre'].strip()
        descripcion     = request.form.get('descripcion', '').strip()
        precio_unitario = request.form['precio_unitario']
        unidad_medida   = request.form['unidad_medida'].strip()
        stock_actual    = request.form.get('stock_actual', '0')

        if not nombre or not precio_unitario or not unidad_medida:
            flash('Nombre, precio y unidad de medida son obligatorios.', 'danger')
            return render_template('productos/form.html', producto=None)

        if float(precio_unitario) < 0:
            flash('El precio no puede ser negativo.', 'danger')
            return render_template('productos/form.html', producto=None)

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

@producto_bp.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@rol_requerido('admin')
def editar(id):
    producto = Producto.query.get_or_404(id)

    if request.method == 'POST':
        nombre          = request.form['nombre'].strip()
        descripcion     = request.form.get('descripcion', '').strip()
        precio_unitario = request.form['precio_unitario']
        unidad_medida   = request.form['unidad_medida'].strip()
        stock_actual    = request.form.get('stock_actual', '0')

        if not nombre or not precio_unitario or not unidad_medida:
            flash('Nombre, precio y unidad de medida son obligatorios.', 'danger')
            return render_template('productos/form.html', producto=producto)

        if float(precio_unitario) < 0:
            flash('El precio no puede ser negativo.', 'danger')
            return render_template('productos/form.html', producto=producto)

        producto.nombre          = nombre
        producto.descripcion     = descripcion
        producto.precio_unitario = precio_unitario
        producto.unidad_medida   = unidad_medida
        producto.stock_actual    = float(stock_actual)

        db.session.commit()
        flash(f'Producto "{producto.nombre}" actualizado.', 'success')
        return redirect(url_for('productos.listar'))

    return render_template('productos/form.html', producto=producto)


# ─── DESACTIVAR PRODUCTO ──────────────────────────────────────────────────────

@producto_bp.route('/productos/desactivar/<int:id>', methods=['POST'])
@login_required
@rol_requerido('admin')
def desactivar(id):
    producto = Producto.query.get_or_404(id)
    producto.activo = False
    db.session.commit()
    flash(f'Producto "{producto.nombre}" desactivado.', 'warning')
    return redirect(url_for('productos.listar'))


# ─── ACTIVAR PRODUCTO ─────────────────────────────────────────────────────────

@producto_bp.route('/productos/activar/<int:id>', methods=['POST'])
@login_required
@rol_requerido('admin')
def activar(id):
    producto = Producto.query.get_or_404(id)
    producto.activo = True
    db.session.commit()
    flash(f'Producto "{producto.nombre}" activado correctamente.', 'success')
    return redirect(url_for('productos.listar'))
