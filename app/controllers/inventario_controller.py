from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.inventario import ElementoInventario
from app.utils.decorators import rol_requerido

inventario_bp = Blueprint('inventario', __name__)


# ─── LISTAR INVENTARIO ────────────────────────────────────────────────────────

@inventario_bp.route('/inventario')
@login_required
def listar():
    categoria = request.args.get('categoria', '')  # filtro opcional por categoría

    query = ElementoInventario.query.filter_by(activo=True)
    if categoria:
        query = query.filter_by(categoria=categoria)

    elementos = query.order_by(ElementoInventario.nombre).all()
    return render_template('inventario/lista.html', elementos=elementos, categoria=categoria)


# ─── NUEVO ELEMENTO ───────────────────────────────────────────────────────────

@inventario_bp.route('/inventario/nuevo', methods=['GET', 'POST'])
@login_required
@rol_requerido('admin', 'operario')
def nuevo():
    if request.method == 'POST':
        nombre        = request.form['nombre']
        categoria     = request.form['categoria']
        stock_actual  = request.form['stock_actual']
        stock_minimo  = request.form['stock_minimo']
        unidad_medida = request.form['unidad_medida']

        elemento = ElementoInventario(
            nombre=nombre,
            categoria=categoria,
            stock_actual=stock_actual,
            stock_minimo=stock_minimo,
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
@rol_requerido('admin', 'operario')
def editar(id):
    elemento = ElementoInventario.query.get_or_404(id)

    if request.method == 'POST':
        elemento.nombre        = request.form['nombre']
        elemento.categoria     = request.form['categoria']
        elemento.stock_actual  = request.form['stock_actual']
        elemento.stock_minimo  = request.form['stock_minimo']
        elemento.unidad_medida = request.form['unidad_medida']

        db.session.commit()
        flash(f'Elemento "{elemento.nombre}" actualizado.', 'success')
        return redirect(url_for('inventario.listar'))

    return render_template('inventario/form.html', elemento=elemento)


# ─── DESACTIVAR ELEMENTO ──────────────────────────────────────────────────────

@inventario_bp.route('/inventario/desactivar/<int:id>', methods=['POST'])
@login_required
@rol_requerido('admin', 'operario')
def desactivar(id):
    elemento = ElementoInventario.query.get_or_404(id)
    elemento.activo = False
    db.session.commit()
    flash(f'Elemento "{elemento.nombre}" desactivado.', 'warning')
    return redirect(url_for('inventario.listar'))