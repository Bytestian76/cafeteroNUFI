from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.movimiento import Movimiento
from app.models.inventario import ElementoInventario
from app.utils.decorators import rol_requerido

movimiento_bp = Blueprint('movimientos', __name__)


# ─── HISTORIAL DE MOVIMIENTOS ─────────────────────────────────────────────────

@movimiento_bp.route('/movimientos')
@login_required
def historial():
    elemento_id = request.args.get('elemento_id', '')
    tipo        = request.args.get('tipo', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')

    query = Movimiento.query

    if elemento_id:
        query = query.filter_by(elemento_id=elemento_id)
    if tipo:
        query = query.filter_by(tipo=tipo)
    if fecha_desde:
        query = query.filter(Movimiento.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Movimiento.fecha <= fecha_hasta)

    movimientos = query.order_by(Movimiento.fecha.desc()).all()
    elementos   = ElementoInventario.query.filter_by(activo=True).order_by(ElementoInventario.nombre).all()

    return render_template('movimientos/historial.html',
                           movimientos=movimientos,
                           elementos=elementos,
                           filtros={'elemento_id': elemento_id, 'tipo': tipo,
                                    'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta})


# ─── REGISTRAR MOVIMIENTO ─────────────────────────────────────────────────────

@movimiento_bp.route('/movimientos/nuevo', methods=['GET', 'POST'])
@login_required
@rol_requerido('admin', 'operario')
def nuevo():
    elementos = ElementoInventario.query.filter_by(activo=True).order_by(ElementoInventario.nombre).all()

    if request.method == 'POST':
        elemento_id = int(request.form['elemento_id'])
        tipo        = request.form['tipo']
        cantidad    = float(request.form['cantidad'])
        observacion = request.form.get('observacion', '')

        elemento = ElementoInventario.query.get_or_404(elemento_id)

        # ── REGLA DE NEGOCIO: validar stock antes de guardar salida ──
        if tipo == 'salida' and cantidad > float(elemento.stock_actual):
            flash(f'Stock insuficiente. Stock actual: {elemento.stock_actual} {elemento.unidad_medida}.', 'danger')
            return render_template('movimientos/nuevo.html', elementos=elementos)

        # ── Actualizar stock_actual ──
        if tipo == 'entrada':
            elemento.stock_actual = float(elemento.stock_actual) + cantidad
        else:
            elemento.stock_actual = float(elemento.stock_actual) - cantidad

        # ── Guardar movimiento ──
        movimiento = Movimiento(
            elemento_id=elemento_id,
            tipo=tipo,
            cantidad=cantidad,
            observacion=observacion,
            usuario_id=current_user.id
        )
        db.session.add(movimiento)
        db.session.commit()

        # ── REGLA DE NEGOCIO: alerta de escasez tras movimiento ──
        if elemento.tiene_alerta():
            flash(f'⚠️ Alerta: "{elemento.nombre}" está por debajo del stock mínimo ({elemento.stock_minimo} {elemento.unidad_medida}).', 'warning')

        flash(f'Movimiento de {tipo} registrado correctamente.', 'success')
        return redirect(url_for('movimientos.historial'))

    return render_template('movimientos/nuevo.html', elementos=elementos)