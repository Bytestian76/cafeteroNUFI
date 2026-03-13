from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models.producto import Producto
from app.utils.decorators import rol_requerido

producto_bp = Blueprint('productos', __name__)


# ─── LISTAR PRODUCTOS ─────────────────────────────────────────────────────────

@producto_bp.route('/productos')
@login_required
def listar():
    productos = Producto.query.order_by(Producto.nombre).all()
    return render_template('productos/lista.html', productos=productos)


# ─── NUEVO PRODUCTO ───────────────────────────────────────────────────────────

@producto_bp.route('/productos/nuevo', methods=['GET', 'POST'])
@login_required
@rol_requerido('admin')
def nuevo():
    if request.method == 'POST':
        nombre          = request.form['nombre']
        descripcion     = request.form.get('descripcion', '')
        precio_unitario = request.form['precio_unitario']
        unidad_medida   = request.form['unidad_medida']

        producto = Producto(
            nombre=nombre,
            descripcion=descripcion,
            precio_unitario=precio_unitario,
            unidad_medida=unidad_medida
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
        producto.nombre          = request.form['nombre']
        producto.descripcion     = request.form.get('descripcion', '')
        producto.precio_unitario = request.form['precio_unitario']
        producto.unidad_medida   = request.form['unidad_medida']

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
