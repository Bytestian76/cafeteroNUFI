# venta_controller.py — Facturación, clientes y generación de PDF individual.
# Rutas principales:
#   /ventas                        → listar facturas con filtros
#   /ventas/nueva                  → crear factura (descuenta stock de productos)
#   /ventas/<id>/anular            → anular factura (restaura stock)
#   /ventas/<id>/detalle           → ver detalle de factura
#   /ventas/<id>/factura           → PDF individual con ReportLab
#   /ventas/clientes               → listado de clientes
#   /ventas/clientes/nuevo|editar  → CRUD de clientes
#   /ventas/clientes/eliminar/<id> → eliminar (solo si no tiene ventas)
from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response, jsonify
from flask_login import login_required
from app import db
from app.models.venta import Cliente, Venta, DetalleVenta
from app.models.producto import Producto
from app.models.temporada import Temporada
from datetime import datetime, timedelta

import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Flowable

import re

venta_bp = Blueprint('ventas', __name__)


# ─── HUB VENTAS ───────────────────────────────────────────────────────────────

@venta_bp.route('/ventas/hub')
@login_required
def hub_ventas():
    return render_template('ventas/hub.html')


POR_PAGINA = 15

# Valida teléfono colombiano: exactamente 10 dígitos, empieza por 3 o 6
_TEL_RE = re.compile(r'^[36]\d{9}$')

def _telefono_valido(tel):
    return bool(_TEL_RE.match(tel))


# Construye URL de paginación conservando filtros activos de la lista de ventas
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
# Filtros: cliente, producto (busca en detalles de la venta), y rango de fechas.
# total_pagina excluye ventas anuladas para reflejar el recaudo real.

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
    # Excluir ventas anuladas del total recaudado
    total_pagina = sum(float(v.total) for v in todas_ventas if not v.anulada)

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
# Proceso:
#   1. Crear registro Venta en estado provisional (flush para obtener ID)
#   2. Por cada línea de producto: validar stock, crear DetalleVenta, descontar stock
#   3. Calcular subtotal, IVA y total; actualizar la Venta
#   4. Si cualquier paso falla: rollback completo (ningún dato queda guardado)
# Stock descontado en Producto.stock_actual → modelo en producto.py

@venta_bp.route('/ventas/nueva', methods=['GET', 'POST'])
@login_required
def nueva():
    # Asegurar que existe el cliente genérico para ventas sin datos
    cf = Cliente.query.filter_by(nombre='Consumidor Final').first()
    if not cf:
        cf = Cliente(nombre='Consumidor Final')
        db.session.add(cf)
        db.session.commit()

    clientes       = Cliente.query.order_by(Cliente.nombre).all()
    productos      = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()
    campana_activa = Temporada.query.filter_by(estado='activa').first()

    if request.method == 'POST':
        cliente_id     = request.form.get('cliente_id')
        producto_ids   = request.form.getlist('producto_id[]')
        cantidades     = request.form.getlist('cantidad[]')
        iva_porcentaje = float(request.form.get('iva_porcentaje', 0))
        campana_id     = request.form.get('campana_id') or None

        if not cliente_id or not producto_ids:
            flash('La factura requiere un cliente y al menos un producto.', 'danger')
            return render_template('ventas/nueva_factura.html', clientes=clientes, productos=productos, campana_activa=campana_activa, cliente_cf_id=cf.id)

        try:
            venta = Venta(cliente_id=cliente_id, subtotal=0, iva_porcentaje=iva_porcentaje, total=0, campana_id=campana_id)
            db.session.add(venta)
            db.session.flush()  # genera venta.id sin hacer commit aún

            subtotal_sum = 0
            for prod_id, cant in zip(producto_ids, cantidades):
                if not prod_id or not cant:
                    continue
                producto = Producto.query.get(int(prod_id))
                if not producto:
                    raise ValueError(f'Producto ID {prod_id} no encontrado.')

                cantidad    = float(cant)
                precio_unit = float(producto.precio_unitario)
                subtotal    = cantidad * precio_unit

                # Validar stock disponible antes de descontar
                if producto.stock_actual is not None and producto.stock_actual < cantidad:
                    flash(
                        f'Stock insuficiente para "{producto.nombre}". '
                        f'Disponible: {float(producto.stock_actual):g} {producto.unidad_medida}, '
                        f'solicitado: {cantidad:g} {producto.unidad_medida}.',
                        'danger'
                    )
                    db.session.rollback()
                    return render_template('ventas/nueva_factura.html', clientes=clientes, productos=productos, campana_activa=campana_activa)

                detalle = DetalleVenta(
                    venta_id=venta.id,
                    producto_id=producto.id,
                    cantidad=cantidad,
                    precio_unit=precio_unit,
                    subtotal=subtotal
                )
                db.session.add(detalle)

                # Descontar del stock del producto → conectado con Producto.stock_actual en producto.py
                if producto.stock_actual is not None:
                    producto.stock_actual = float(producto.stock_actual) - cantidad

                subtotal_sum += subtotal

            # Calcular IVA y total final
            iva_monto   = subtotal_sum * iva_porcentaje / 100
            total_final = subtotal_sum + iva_monto
            venta.subtotal       = subtotal_sum
            venta.total          = total_final
            db.session.commit()
            flash(f'Factura #{venta.id} registrada correctamente. Total: ${total_final:,.2f}', 'success')
            return redirect(url_for('ventas.listar'))

        except Exception:
            db.session.rollback()
            flash('Error al registrar la factura. No se guardó ningún dato.', 'danger')
            return render_template('ventas/nueva_factura.html', clientes=clientes, productos=productos, campana_activa=campana_activa, cliente_cf_id=cf.id)

    return render_template('ventas/nueva_factura.html', clientes=clientes, productos=productos, campana_activa=campana_activa, cliente_cf_id=cf.id)


# ─── LISTAR CLIENTES ──────────────────────────────────────────────────────────

@venta_bp.route('/ventas/clientes')
@login_required
def listar_clientes():
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    cf       = Cliente.query.filter_by(nombre='Consumidor Final').first()
    cf_id    = cf.id if cf else None
    return render_template('ventas/clientes.html', clientes=clientes, cf_id=cf_id)


# ─── NUEVO CLIENTE ────────────────────────────────────────────────────────────
# origen='nueva' indica que el usuario llegó desde el formulario de nueva factura;
# al guardar el cliente lo redirige de vuelta a /ventas/nueva en lugar del listado.
# Valida el teléfono con _telefono_valido() (regex colombiano, línea 25).

@venta_bp.route('/ventas/clientes/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_cliente():
    origen = request.args.get('origen', '')

    if request.method == 'POST':
        nombre    = request.form['nombre'].strip()
        documento = request.form.get('documento', '').strip()
        telefono  = request.form.get('telefono', '').strip()
        direccion = request.form.get('direccion', '').strip()
        origen    = request.form.get('origen', '')

        if not nombre:
            flash('El nombre del cliente es obligatorio.', 'danger')
            return render_template('ventas/form_cliente.html', cliente=None, origen=origen)

        if not telefono:
            flash('El teléfono de contacto es obligatorio.', 'danger')
            return render_template('ventas/form_cliente.html', cliente=None, origen=origen)

        if not _telefono_valido(telefono):
            flash('El teléfono debe tener exactamente 10 dígitos y empezar por 3 (celular) o 6 (fijo).', 'danger')
            return render_template('ventas/form_cliente.html', cliente=None, origen=origen)

        cliente = Cliente(nombre=nombre, documento=documento,
                          telefono=telefono, direccion=direccion)
        db.session.add(cliente)
        db.session.commit()
        flash(f'Cliente "{nombre}" registrado correctamente.', 'success')

        # Volver a nueva factura si se llegó desde allí
        if origen == 'nueva':
            return redirect(url_for('ventas.nueva'))
        return redirect(url_for('ventas.listar_clientes'))

    return render_template('ventas/form_cliente.html', cliente=None, origen=origen)


# ─── EDITAR CLIENTE ───────────────────────────────────────────────────────────

@venta_bp.route('/ventas/clientes/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    if request.method == 'POST':
        nombre   = request.form['nombre'].strip()
        telefono = request.form.get('telefono', '').strip()

        if not nombre:
            flash('El nombre del cliente es obligatorio.', 'danger')
            return render_template('ventas/form_cliente.html', cliente=cliente, origen='')

        if not telefono:
            flash('El teléfono de contacto es obligatorio.', 'danger')
            return render_template('ventas/form_cliente.html', cliente=cliente, origen='')

        if not _telefono_valido(telefono):
            flash('El teléfono debe tener exactamente 10 dígitos y empezar por 3 (celular) o 6 (fijo).', 'danger')
            return render_template('ventas/form_cliente.html', cliente=cliente, origen='')

        cliente.nombre    = nombre
        cliente.documento = request.form.get('documento', '').strip()
        cliente.telefono  = telefono
        cliente.direccion = request.form.get('direccion', '').strip()

        db.session.commit()
        flash(f'Cliente "{cliente.nombre}" actualizado.', 'success')
        return redirect(url_for('ventas.listar_clientes'))

    return render_template('ventas/form_cliente.html', cliente=cliente, origen='')


# ─── ELIMINAR CLIENTE ─────────────────────────────────────────────────────────
# Bloquea la eliminación si el cliente tiene ventas registradas (integridad referencial).

@venta_bp.route('/ventas/clientes/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if cliente.nombre == 'Consumidor Final':
        msg = 'El cliente "Consumidor Final" es del sistema y no se puede eliminar.'
        if es_ajax:
            return jsonify({'ok': False, 'msg': msg, 'categoria': 'warning'})
        flash(msg, 'warning')
        return redirect(url_for('ventas.listar_clientes'))

    if cliente.ventas:
        msg = f'No se puede eliminar a "{cliente.nombre}" porque tiene ventas registradas.'
        if es_ajax:
            return jsonify({'ok': False, 'msg': msg, 'categoria': 'danger'})
        flash(msg, 'danger')
        return redirect(url_for('ventas.listar_clientes'))

    nombre = cliente.nombre
    db.session.delete(cliente)
    db.session.commit()
    msg = f'Cliente "{nombre}" eliminado.'
    if es_ajax:
        return jsonify({'ok': True, 'msg': msg, 'categoria': 'success'})
    flash(msg, 'success')
    return redirect(url_for('ventas.listar_clientes'))


# ─── DETALLE DE VENTA ─────────────────────────────────────────────────────────

@venta_bp.route('/ventas/<int:id>/detalle')
@login_required
def detalle(id):
    venta = Venta.query.get_or_404(id)
    return render_template('ventas/detalle.html', venta=venta)


# ─── ANULAR VENTA ─────────────────────────────────────────────────────────────
# Restaura el stock de cada producto del detalle sumando la cantidad vendida.
# Marca la venta como anulada y registra la fecha de anulación.
# Conectado con Producto.stock_actual en producto.py.

@venta_bp.route('/ventas/<int:id>/anular', methods=['POST'])
@login_required
def anular(id):
    venta = Venta.query.get_or_404(id)

    if venta.anulada:
        msg = 'Esta venta ya estaba anulada.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'msg': msg, 'categoria': 'warning'})
        flash(msg, 'warning')
        return redirect(url_for('ventas.listar'))

    # Restaurar stock de cada producto → conectado con Producto.stock_actual en producto.py
    for detalle in venta.detalles:
        if detalle.producto:
            detalle.producto.stock_actual = float(detalle.producto.stock_actual) + float(detalle.cantidad)

    venta.anulada         = True
    venta.fecha_anulacion = datetime.now()
    db.session.commit()

    msg = f'Factura #{venta.id} anulada correctamente. El stock fue restaurado.'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'msg': msg, 'categoria': 'success'})
    flash(msg, 'success')
    return redirect(url_for('ventas.listar'))


# ─── FACTURA PDF INDIVIDUAL ───────────────────────────────────────────────────
# Genera un PDF A4 de la factura usando ReportLab.
# Estructura del documento:
#   1. Encabezado (logo CN + nombre empresa + número de factura)
#   2. Datos del cliente y detalles de la factura (fecha, pago)
#   3. Tabla de productos (descripción, cantidad, unidad, precio, subtotal)
#   4. Totales (subtotal + IVA + total en caja verde)
#   5. Pie de página
# draw_accent dibuja la barra lateral verde degradada en cada página.

@venta_bp.route('/ventas/<int:id>/factura')
@login_required
def factura_pdf(id):
    venta = Venta.query.get_or_404(id)

    # ── Paleta Verde Naturaleza ───────────────────────────────────────────────
    CV       = colors.HexColor('#2E7D42')   # verde primario
    CV_MED   = colors.HexColor('#43A047')   # verde medio
    CV_TENUE = colors.HexColor('#F1F8F2')   # fondo filas pares
    C_LINEA  = colors.HexColor('#b8d4bc')   # divisores
    C_TEXTO  = colors.HexColor('#2E4A32')   # texto principal
    C_LABEL  = colors.HexColor('#6a8a6e')   # etiquetas / secundario
    C_BLANCO = colors.white

    # Formatea valor como peso colombiano: $ 31.000
    def cop(valor):
        return '$ ' + f'{int(round(float(valor))):,}'.replace(',', '.')

    # Dibuja la barra lateral izquierda con degradado verde (se aplica en cada página)
    def draw_accent(canvas, doc):
        canvas.saveState()
        steps = 50
        page_h = doc.pagesize[1]
        for i in range(steps):
            t = i / (steps - 1)
            if t < 0.5:
                r1, g1, b1 = 0x2E, 0x7D, 0x42
                r2, g2, b2 = 0x43, 0xA0, 0x47
                tt = t * 2
            else:
                r1, g1, b1 = 0x43, 0xA0, 0x47
                r2, g2, b2 = 0xA5, 0xD6, 0xA7
                tt = (t - 0.5) * 2
            r = int(r1 + (r2 - r1) * tt)
            g = int(g1 + (g2 - g1) * tt)
            b = int(b1 + (b2 - b1) * tt)
            canvas.setFillColor(colors.HexColor(f'#{r:02x}{g:02x}{b:02x}'))
            y = page_h * (1 - (i + 1) / steps)
            canvas.rect(0, y, 5, page_h / steps + 1, fill=1, stroke=0)
        canvas.restoreState()

    # Flowable personalizado: círculo verde con las letras "CN"
    class LogoCircle(Flowable):
        def __init__(self, sz=30):
            super().__init__()
            self.width  = sz
            self.height = sz
            self._sz    = sz

        def draw(self):
            r = self._sz / 2
            self.canv.setFillColor(colors.HexColor('#2E7D42'))
            self.canv.circle(r, r, r, fill=1, stroke=0)
            self.canv.setFillColor(colors.white)
            self.canv.setFont('Helvetica-Bold', 10)
            self.canv.drawCentredString(r, r - 4, 'CN')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=14*mm, bottomMargin=14*mm,
        leftMargin=22*mm, rightMargin=16*mm
    )

    base = getSampleStyleSheet()
    W    = A4[0] - 38*mm   # ancho útil del documento

    # Fábrica de estilos: crea un ParagraphStyle basado en 'Normal' con parámetros extras
    def S(name, **kw):
        return ParagraphStyle(name, parent=base['Normal'],
                              leading=kw.pop('leading', kw.get('fontSize', 9) * 1.5),
                              **kw)

    s_empresa    = S('emp', fontSize=14, fontName='Helvetica-Bold', textColor=C_TEXTO)
    s_ubicacion  = S('ubi', fontSize=9,  textColor=C_LABEL)
    s_fac_titulo = S('ftt', fontSize=24, fontName='Helvetica-Bold',
                     textColor=CV, alignment=TA_RIGHT)
    s_fac_num    = S('ftn', fontSize=11, textColor=C_LABEL, alignment=TA_RIGHT)
    s_etiqueta   = S('eta', fontSize=7, fontName='Helvetica-Bold', textColor=C_LABEL,
                     spaceAfter=3, leading=10)
    s_dato_bold  = S('dbo', fontSize=11, fontName='Helvetica-Bold', textColor=C_TEXTO)
    s_dato       = S('dat', fontSize=9,  textColor=C_TEXTO, spaceAfter=1)
    s_th         = S('th',  fontSize=8, fontName='Helvetica-Bold',
                     textColor=C_BLANCO, alignment=TA_CENTER)
    s_th_izq     = S('thi', fontSize=8, fontName='Helvetica-Bold',
                     textColor=C_BLANCO, alignment=TA_LEFT)
    s_td_n       = S('tdn', fontSize=9,  textColor=C_TEXTO, alignment=TA_LEFT)
    s_td_c       = S('tdc', fontSize=9,  textColor=C_TEXTO, alignment=TA_CENTER)
    s_td_r       = S('tdr', fontSize=9,  textColor=C_TEXTO, alignment=TA_RIGHT)
    s_lbl_tot    = S('lt',  fontSize=9,  textColor=C_LABEL, alignment=TA_CENTER)
    s_val_tot    = S('vt',  fontSize=9,  fontName='Helvetica-Bold',
                     textColor=C_TEXTO, alignment=TA_CENTER)
    s_gran_lbl   = S('gl',  fontSize=11, fontName='Helvetica-Bold',
                     textColor=C_BLANCO, alignment=TA_LEFT)
    s_gran_val   = S('gv',  fontSize=12, fontName='Helvetica-Bold',
                     textColor=C_BLANCO, alignment=TA_RIGHT)
    s_pie_it     = S('pii', fontSize=10, fontName='Helvetica-Oblique',
                     textColor=C_LABEL, alignment=TA_CENTER)
    s_pie        = S('pie', fontSize=8,  textColor=C_LABEL, alignment=TA_CENTER)

    bloques = []
    fecha_str = venta.fecha.strftime('%d/%m/%Y') if venta.fecha else '—'
    hora_str  = venta.fecha.strftime('%I:%M %p') if venta.fecha else '—'

    # ══ 1. ENCABEZADO ═════════════════════════════════════════════════════════
    logo = LogoCircle(30)
    t_brand = Table([[
        logo,
        [Paragraph('El Cafetero de Nufi', s_empresa),
         Paragraph('Barbosa, Santander — Colombia', s_ubicacion)]
    ]], colWidths=[34, W * 0.55 - 34])
    t_brand.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING',   (1, 0), (1, 0),   8),
    ]))

    t_header = Table([[
        t_brand,
        [Paragraph('FACTURA', s_fac_titulo),
         Paragraph(f'N.° {venta.id:04d}', s_fac_num)]
    ]], colWidths=[W * 0.55, W * 0.45])
    t_header.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',   (0, 0), (0, 0),   0),
        ('RIGHTPADDING',  (0, 0), (0, 0),   8),
        ('LEFTPADDING',   (1, 0), (1, 0),   8),
        ('RIGHTPADDING',  (1, 0), (1, 0),   0),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    bloques.append(t_header)
    bloques.append(HRFlowable(width='100%', thickness=0.8, color=C_LINEA,
                              spaceBefore=3*mm, spaceAfter=3*mm))

    # ══ 2. DATOS CLIENTE / DETALLES ══════════════════════════════════════════
    cli = venta.cliente
    izq = [
        Paragraph('FACTURADO A', s_etiqueta),
        Paragraph(cli.nombre, s_dato_bold),
    ]
    if cli.documento:
        izq.append(Paragraph(f'Documento: {cli.documento}', s_dato))
    if cli.telefono:
        izq.append(Paragraph(f'Teléfono: {cli.telefono}', s_dato))
    if cli.direccion:
        izq.append(Paragraph(f'Dirección: {cli.direccion}', s_dato))

    der = [
        Paragraph('DETALLES DE FACTURA', s_etiqueta),
        Paragraph(f'Fecha: {fecha_str}', s_dato),
        Paragraph(f'Hora: {hora_str}', s_dato),
        Paragraph('Pago: Contado', s_dato),
        Paragraph(f'N.° Factura: {venta.id:04d}', s_dato),
    ]

    t_info = Table([[izq, der]], colWidths=[W * 0.55, W * 0.45])
    t_info.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    bloques.append(t_info)
    bloques.append(HRFlowable(width='100%', thickness=0.8, color=C_LINEA,
                              spaceBefore=4*mm, spaceAfter=4*mm))

    # ══ 3. TABLA DE PRODUCTOS ═════════════════════════════════════════════════
    col_w = [W*0.38, W*0.10, W*0.13, W*0.20, W*0.19]
    filas = [[
        Paragraph('Descripción', s_th),
        Paragraph('Cant.',       s_th),
        Paragraph('Unidad',      s_th),
        Paragraph('P. Unitario', s_th),
        Paragraph('Subtotal',    s_th),
    ]]
    for d in venta.detalles:
        nombre_prod = d.producto.nombre if d.producto else '(producto eliminado)'
        unidad_prod = (d.producto.unidad_medida or '—') if d.producto else '—'
        cant = int(d.cantidad) if float(d.cantidad) == int(float(d.cantidad)) else float(d.cantidad)
        filas.append([
            Paragraph(nombre_prod,        s_td_c),
            Paragraph(str(cant),          s_td_c),
            Paragraph(unidad_prod,        s_td_c),
            Paragraph(cop(d.precio_unit), s_td_c),
            Paragraph(cop(d.subtotal),    s_td_c),
        ])

    t_prods = Table(filas, colWidths=col_w, repeatRows=1)
    t_prods.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1,  0), CV),
        ('TOPPADDING',    (0, 0), (-1,  0), 9),
        ('BOTTOMPADDING', (0, 0), (-1,  0), 9),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_BLANCO, CV_TENUE]),
        ('TOPPADDING',    (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('LEFTPADDING',   (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW',     (0, 1), (-1, -2), 0.4, C_LINEA),
    ]))
    bloques.append(t_prods)
    bloques.append(Spacer(1, 4*mm))

    # ══ 4. TOTALES ════════════════════════════════════════════════════════════
    subtotal_val  = float(venta.subtotal) if venta.subtotal else float(venta.total)
    iva_pct       = float(venta.iva_porcentaje) if venta.iva_porcentaje else 0
    iva_monto_val = float(venta.total) - subtotal_val

    # Filas de subtotal e IVA alineadas a la derecha
    t_sub = Table([
        ['', Paragraph('Subtotal',          s_lbl_tot), Paragraph(cop(subtotal_val),  s_val_tot)],
        ['', Paragraph(f'IVA ({iva_pct:g}%)', s_lbl_tot), Paragraph(cop(iva_monto_val), s_val_tot)],
    ], colWidths=[W*0.61, W*0.20, W*0.19])
    t_sub.setStyle(TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
    ]))

    # Caja verde de total general
    t_grand = Table([[
        Paragraph('TOTAL A PAGAR',      s_gran_lbl),
        Paragraph(cop(float(venta.total)), s_gran_val),
    ]], colWidths=[W*0.52, W*0.48])
    t_grand.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), CV),
        ('TOPPADDING',    (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING',   (0, 0), (0,  0),  16),
        ('RIGHTPADDING',  (1, 0), (1,  0),  16),
        ('LEFTPADDING',   (1, 0), (1,  0),  10),
        ('RIGHTPADDING',  (0, 0), (0,  0),  10),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ROUNDEDCORNERS',(0, 0), (-1, -1), 6),
    ]))

    bloques.append(t_sub)
    bloques.append(Spacer(1, 3*mm))
    bloques.append(t_grand)
    bloques.append(Spacer(1, 10*mm))

    # ══ 5. PIE DE PÁGINA ══════════════════════════════════════════════════════
    bloques.append(HRFlowable(width='100%', thickness=0.8, color=C_LINEA,
                              spaceAfter=3*mm))
    bloques.append(Paragraph('¡Gracias por su compra!', s_pie_it))
    bloques.append(Spacer(1, 2*mm))
    bloques.append(Paragraph(
        'El Cafetero de Nufi  ·  Barbosa, Santander, Colombia',
        s_pie
    ))

    doc.build(bloques, onFirstPage=draw_accent, onLaterPages=draw_accent)
    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers['Content-Type']        = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=factura_{venta.id:04d}.pdf'
    return response
