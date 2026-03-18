from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models.venta import Cliente, Venta, DetalleVenta
from app.models.producto import Producto
from app.utils.decorators import rol_requerido
from datetime import datetime, timedelta

venta_bp = Blueprint('ventas', __name__)

POR_PAGINA = 15


def _url_pagina(pagina, cliente_id='', producto_id='', fecha_desde='', fecha_hasta=''):
    params = f'pagina={pagina}'
    if cliente_id:
        params += f'&cliente_id={cliente_id}'
    if producto_id:
        params += f'&producto_id={producto_id}'
    if fecha_desde:
        params += f'&fecha_desde={fecha_desde}'
    if fecha_hasta:
        params += f'&fecha_hasta={fecha_hasta}'
    return f'/ventas?{params}'


# ─── LISTAR VENTAS ────────────────────────────────────────────────────────────

@venta_bp.route('/ventas')
@login_required
def listar():
    cliente_id  = request.args.get('cliente_id', '')
    producto_id = request.args.get('producto_id', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')
    pagina      = request.args.get('pagina', 1, type=int)

    query = Venta.query

    if cliente_id:
        query = query.filter_by(cliente_id=cliente_id)

    # Filtro por producto: ventas que contengan ese producto en sus detalles
    if producto_id:
        query = query.join(DetalleVenta).filter(DetalleVenta.producto_id == producto_id)

    if fecha_desde:
        try:
            dt_desde = datetime.strptime(fecha_desde, '%Y-%m-%d')
            query = query.filter(Venta.fecha >= dt_desde)
        except ValueError:
            pass

    if fecha_hasta:
        try:
            dt_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            query = query.filter(Venta.fecha <= dt_hasta)
        except ValueError:
            pass

    paginacion = query.order_by(Venta.fecha.desc()).paginate(
        page=pagina, per_page=POR_PAGINA, error_out=False
    )

    todas_ventas = query.all()
    total_pagina = sum(float(v.total) for v in todas_ventas)

    clientes  = Cliente.query.order_by(Cliente.nombre).all()
    productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()

    url_anterior  = _url_pagina(paginacion.prev_num, cliente_id, producto_id, fecha_desde, fecha_hasta) if paginacion.has_prev else '#'
    url_siguiente = _url_pagina(paginacion.next_num, cliente_id, producto_id, fecha_desde, fecha_hasta) if paginacion.has_next else '#'

    return render_template('ventas/lista.html',
                           ventas=paginacion.items,
                           paginacion=paginacion,
                           clientes=clientes,
                           productos=productos,
                           total_pagina=total_pagina,
                           filtros={'cliente_id': cliente_id,
                                    'producto_id': producto_id,
                                    'fecha_desde': fecha_desde,
                                    'fecha_hasta': fecha_hasta},
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
        nombre    = request.form['nombre'].strip()
        documento = request.form.get('documento', '').strip()
        telefono  = request.form.get('telefono', '').strip()
        direccion = request.form.get('direccion', '').strip()

        if not nombre:
            flash('El nombre del cliente es obligatorio.', 'danger')
            return render_template('ventas/form_cliente.html', cliente=None)

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
        nombre = request.form['nombre'].strip()
        if not nombre:
            flash('El nombre del cliente es obligatorio.', 'danger')
            return render_template('ventas/form_cliente.html', cliente=cliente)

        cliente.nombre    = nombre
        cliente.documento = request.form.get('documento', '').strip()
        cliente.telefono  = request.form.get('telefono', '').strip()
        cliente.direccion = request.form.get('direccion', '').strip()

        db.session.commit()
        flash(f'Cliente "{cliente.nombre}" actualizado.', 'success')
        return redirect(url_for('ventas.listar_clientes'))

    return render_template('ventas/form_cliente.html', cliente=cliente)
