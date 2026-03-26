# campana_controller.py — Gestión de campañas productivas (siembra → venta).
# Una campaña agrupa movimientos de inventario y ventas para calcular rentabilidad real.
# Restricción: solo puede haber una campaña activa al mismo tiempo.
# Rutas: /campanas (lista), /campanas/nueva, /campanas/<id>/cerrar, /campanas/<id>
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.temporada import Temporada
from datetime import date, datetime

campana_bp = Blueprint('campanas', __name__)


def _campana_activa():
    """Devuelve la campaña activa actual o None. Usada en controladores externos."""
    return Temporada.query.filter_by(estado='activa').first()


# ─── LISTAR CAMPAÑAS ──────────────────────────────────────────────────────────

@campana_bp.route('/campanas')
@login_required
def listar():
    campanas = Temporada.query.order_by(Temporada.fecha_inicio.desc()).all()
    activa   = _campana_activa()
    return render_template('campanas/lista.html', campanas=campanas, activa=activa)


# ─── NUEVA CAMPAÑA ────────────────────────────────────────────────────────────
# Bloquea la creación si ya existe una campaña activa.

@campana_bp.route('/campanas/nueva', methods=['GET', 'POST'])
@login_required
def nueva():
    activa = _campana_activa()
    if activa:
        flash(f'Ya existe una temporada activa: "{activa.nombre}". Ciérrala antes de crear una nueva.', 'warning')
        return redirect(url_for('campanas.listar'))

    if request.method == 'POST':
        nombre               = request.form.get('nombre', '').strip()
        descripcion          = request.form.get('descripcion', '').strip() or None
        fecha_inicio         = request.form.get('fecha_inicio')
        presupuesto_inicial  = request.form.get('presupuesto_inicial', '0').strip() or '0'

        if not nombre or not fecha_inicio:
            flash('El nombre y la fecha de inicio son obligatorios.', 'danger')
            return render_template('campanas/form.html')

        try:
            fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        except ValueError:
            flash('Fecha de inicio inválida.', 'danger')
            return render_template('campanas/form.html')

        try:
            presupuesto_inicial = float(presupuesto_inicial)
            if presupuesto_inicial < 0:
                presupuesto_inicial = 0
        except ValueError:
            presupuesto_inicial = 0

        campana = Temporada(
            nombre=nombre,
            descripcion=descripcion,
            fecha_inicio=fecha_inicio_dt,
            presupuesto_inicial=presupuesto_inicial,
            estado='activa',
            usuario_id=current_user.id
        )
        db.session.add(campana)
        db.session.commit()
        flash(f'Temporada "{nombre}" creada correctamente.', 'success')
        return redirect(url_for('campanas.listar'))

    return render_template('campanas/form.html')


# ─── CERRAR CAMPAÑA ───────────────────────────────────────────────────────────
# Registra la fecha de cierre y cambia el estado a 'cerrada'.

@campana_bp.route('/campanas/<int:id>/cerrar', methods=['POST'])
@login_required
def cerrar(id):
    campana = Temporada.query.get_or_404(id)

    if campana.estado == 'cerrada':
        flash('Esta temporada ya está cerrada.', 'warning')
        return redirect(url_for('campanas.listar'))

    campana.estado    = 'cerrada'
    campana.fecha_fin = date.today()
    db.session.commit()
    flash(f'Temporada "{campana.nombre}" cerrada. Balance final: ${campana.balance:,.2f}', 'success')
    return redirect(url_for('campanas.detalle', id=id))


# ─── DETALLE DE CAMPAÑA ───────────────────────────────────────────────────────
# Muestra el resumen financiero, movimientos y ventas asociados.

@campana_bp.route('/campanas/<int:id>')
@login_required
def detalle(id):
    campana = Temporada.query.get_or_404(id)
    return render_template('campanas/detalle.html', campana=campana)
