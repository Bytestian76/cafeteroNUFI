from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.venta import Cliente, Venta, DetalleVenta
from app.models.producto import Producto
from app.utils.decorators import rol_requerido

venta_bp = Blueprint('ventas', __name__)

POR_PAGINA = 15


# ─── LISTAR VENTAS ────────────────────────────────────────────────────────────

@venta_bp.route('/ventas')
@login_required
def listar():
    pagina   = request.args.get('pagina', 1, type=int)
    clientes = Cliente.query.order_by(Cliente.nombre).all()

    paginacion = Venta.query.order_by(Venta.fecha.desc()).paginate(
        page=pagina, per_page=POR_PAGINA, error_out=False
    )

    url_anterior  = f'/ventas?pagina={paginacion.prev_num}' if paginacion.has_prev else '#'
    url_siguiente = f'/ventas?pagina={paginacion.next_num}' if paginacion.has_next else '#'

    return render_template('ventas/lista.html',
                           ventas=paginacion.items,
                           paginacion=paginacion,
                           clientes=clientes,
                           url_anterior=url_anterior,
                           url_siguiente=url_siguiente)


# ─── NUEVA FACTURA ────────────────────────────────────────────────────────────

@venta_bp.route('/ventas/nueva', methods=['GET', 'POST'])
@login_required
@rol_requerido('admin')
def nueva():
    clientes  = Cliente.query.order_by(Cliente.nombre).all()
    productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()

    if request.method == 'POST':
        cliente_id   = request.form.get('cliente_id')
        producto_ids = request.form.getlist('producto_id[]')
        cantidades   = request.form.getlist('cantidad[]')

        if not cliente_id or not producto_ids:
            flash('La factura requiere un cliente y al menos un producto.', 'danger')
            return render_template('ventas/nueva_factura.html', clientes=clientes, productos=productos)

        try:
            venta = Venta(cliente_id=cliente_id, total=0)
            db.session.add(venta)
            db.session.flush()

            total = 0
            for prod_id, cant in zip(producto_ids, cantidades):
                if not prod_id or not cant:
                    continue
                producto    = Producto.query.get(int(prod_id))
                cantidad    = float(cant)
                precio_unit = float(producto.precio_unitario)
                subtotal    = cantidad * precio_unit

                detalle = DetalleVenta(
                    venta_id=venta.id,
                    producto_id=producto.id,
                    cantidad=cantidad,
                    precio_unit=precio_unit,
                    subtotal=subtotal
                )
                db.session.add(detalle)
                total += subtotal

            venta.total = total
            db.session.commit()
            flash(f'Factura #{venta.id} registrada correctamente. Total: ${total:,.2f}', 'success')
            return redirect(url_for('ventas.listar'))

        except Exception:
            db.session.rollback()
            flash('Error al registrar la factura. No se guardó ningún dato.', 'danger')
            return render_template('ventas/nueva_factura.html', clientes=clientes, productos=productos)

    return render_template('ventas/nueva_factura.html', clientes=clientes, productos=productos)


# ─── LISTAR CLIENTES ──────────────────────────────────────────────────────────

@venta_bp.route('/ventas/clientes')
@login_required
def listar_clientes():
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    return render_template('ventas/clientes.html', clientes=clientes)


# ─── NUEVO CLIENTE ────────────────────────────────────────────────────────────

@venta_bp.route('/ventas/clientes/nuevo', methods=['GET', 'POST'])
@login_required
@rol_requerido('admin')
def nuevo_cliente():
    if request.method == 'POST':
        nombre    = request.form['nombre']
        documento = request.form.get('documento', '')
        telefono  = request.form.get('telefono', '')
        direccion = request.form.get('direccion', '')

        cliente = Cliente(nombre=nombre, documento=documento,
                          telefono=telefono, direccion=direccion)
        db.session.add(cliente)
        db.session.commit()
        flash(f'Cliente "{nombre}" registrado correctamente.', 'success')
        return redirect(url_for('ventas.listar_clientes'))

    return render_template('ventas/form_cliente.html', cliente=None)


# ─── EDITAR CLIENTE ───────────────────────────────────────────────────────────

@venta_bp.route('/ventas/clientes/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@rol_requerido('admin')
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    if request.method == 'POST':
        cliente.nombre    = request.form['nombre']
        cliente.documento = request.form.get('documento', '')
        cliente.telefono  = request.form.get('telefono', '')
        cliente.direccion = request.form.get('direccion', '')

        db.session.commit()
        flash(f'Cliente "{cliente.nombre}" actualizado.', 'success')
        return redirect(url_for('ventas.listar_clientes'))

    return render_template('ventas/form_cliente.html', cliente=cliente)
