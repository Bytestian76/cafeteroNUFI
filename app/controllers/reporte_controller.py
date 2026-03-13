from flask import Blueprint, make_response, request
from flask_login import login_required
from app.models.inventario import ElementoInventario
from app.models.movimiento import Movimiento
from app.models.venta import Venta, Cliente
from app.utils.decorators import rol_requerido
from datetime import datetime, timedelta

import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

reporte_bp = Blueprint('reportes', __name__)


# ─── HELPER: convertir fechas string a datetime ───────────────────────────────

def parsear_fechas(fecha_desde_str, fecha_hasta_str):
    dt_desde = None
    dt_hasta = None
    if fecha_desde_str:
        try:
            dt_desde = datetime.strptime(fecha_desde_str, '%Y-%m-%d')
        except ValueError:
            pass
    if fecha_hasta_str:
        try:
            dt_hasta = datetime.strptime(fecha_hasta_str, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
        except ValueError:
            pass
    return dt_desde, dt_hasta


# ─── HELPER: estilo base de tabla ─────────────────────────────────────────────

def estilo_tabla():
    return TableStyle([
        ('BACKGROUND',     (0, 0), (-1, 0),  colors.HexColor('#2c7a4b')),
        ('TEXTCOLOR',      (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',       (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',       (0, 0), (-1, 0),  10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f2f2')]),
        ('FONTSIZE',       (0, 1), (-1, -1), 9),
        ('GRID',           (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('TOPPADDING',     (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 6),
        ('LEFTPADDING',    (0, 0), (-1, -1), 8),
    ])


# ─── PDF INVENTARIO ───────────────────────────────────────────────────────────

@reporte_bp.route('/reportes/inventario/pdf')
@login_required
@rol_requerido('admin')
def inventario_pdf():
    categoria = request.args.get('categoria', '')
    alerta    = request.args.get('alerta', '')

    query = ElementoInventario.query.filter_by(activo=True)
    if categoria:
        query = query.filter_by(categoria=categoria)

    elementos = query.order_by(ElementoInventario.nombre).all()
    if alerta == '1':
        elementos = [e for e in elementos if e.tiene_alerta()]

    con_escasez = sum(1 for e in elementos if e.tiene_alerta())

    buffer  = io.BytesIO()
    doc     = SimpleDocTemplate(buffer, pagesize=A4,
                                topMargin=40, bottomMargin=40,
                                leftMargin=40, rightMargin=40)
    styles  = getSampleStyleSheet()
    bloques = []

    bloques.append(Paragraph("El Cafetero de Nufi", styles['Title']))
    bloques.append(Paragraph("Reporte de Inventario", styles['Heading2']))
    bloques.append(Spacer(1, 6))

    fecha_generado = datetime.now().strftime('%d/%m/%Y %H:%M')
    bloques.append(Paragraph(f"Generado: {fecha_generado}", styles['Normal']))
    if categoria:
        bloques.append(Paragraph(f"Categoría: {categoria}", styles['Normal']))
    if alerta == '1':
        bloques.append(Paragraph("Filtro: Solo elementos con alerta de escasez", styles['Normal']))
    bloques.append(Paragraph(
        f"Total elementos: {len(elementos)}  |  Con escasez: {con_escasez}",
        styles['Normal']
    ))
    bloques.append(Spacer(1, 12))

    encabezado = [['Nombre', 'Categoría', 'Unidad', 'Stock Actual', 'Stock Mínimo', 'Estado']]
    filas = []
    for e in elementos:
        estado = 'Escasez' if e.tiene_alerta() else 'OK'
        filas.append([
            e.nombre, e.categoria, e.unidad_medida,
            str(e.stock_actual), str(e.stock_minimo), estado
        ])

    tabla = Table(encabezado + filas, colWidths=[140, 90, 70, 70, 70, 60])
    tabla.setStyle(estilo_tabla())

    for i, e in enumerate(elementos, start=1):
        if e.tiene_alerta():
            tabla.setStyle(TableStyle([
                ('TEXTCOLOR', (5, i), (5, i), colors.red),
                ('FONTNAME',  (5, i), (5, i), 'Helvetica-Bold'),
            ]))

    bloques.append(tabla)
    doc.build(bloques)
    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=reporte_inventario.pdf'
    return response


# ─── PDF MOVIMIENTOS ──────────────────────────────────────────────────────────

@reporte_bp.route('/reportes/movimientos/pdf')
@login_required
@rol_requerido('admin')
def movimientos_pdf():
    elemento_id = request.args.get('elemento_id', '')
    tipo        = request.args.get('tipo', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')

    query = Movimiento.query
    if elemento_id:
        query = query.filter_by(elemento_id=elemento_id)
    if tipo:
        query = query.filter_by(tipo=tipo)

    dt_desde, dt_hasta = parsear_fechas(fecha_desde, fecha_hasta)
    if dt_desde:
        query = query.filter(Movimiento.fecha >= dt_desde)
    if dt_hasta:
        query = query.filter(Movimiento.fecha <= dt_hasta)

    movimientos_lista = query.order_by(Movimiento.fecha.desc()).all()
    total_entradas = sum(float(m.cantidad) for m in movimientos_lista if m.tipo == 'entrada')
    total_salidas  = sum(float(m.cantidad) for m in movimientos_lista if m.tipo == 'salida')

    buffer  = io.BytesIO()
    doc     = SimpleDocTemplate(buffer, pagesize=A4,
                                topMargin=40, bottomMargin=40,
                                leftMargin=40, rightMargin=40)
    styles  = getSampleStyleSheet()
    bloques = []

    bloques.append(Paragraph("El Cafetero de Nufi", styles['Title']))
    bloques.append(Paragraph("Reporte de Movimientos", styles['Heading2']))
    bloques.append(Spacer(1, 6))

    fecha_generado = datetime.now().strftime('%d/%m/%Y %H:%M')
    bloques.append(Paragraph(f"Generado: {fecha_generado}", styles['Normal']))
    if fecha_desde:
        bloques.append(Paragraph(f"Desde: {fecha_desde}", styles['Normal']))
    if fecha_hasta:
        bloques.append(Paragraph(f"Hasta: {fecha_hasta}", styles['Normal']))
    bloques.append(Paragraph(
        f"Total movimientos: {len(movimientos_lista)}  |  "
        f"Entradas: {total_entradas}  |  Salidas: {total_salidas}",
        styles['Normal']
    ))
    bloques.append(Spacer(1, 12))

    encabezado = [['Fecha', 'Elemento', 'Tipo', 'Cantidad', 'Observación', 'Usuario']]
    filas = []
    for m in movimientos_lista:
        filas.append([
            m.fecha.strftime('%d/%m/%Y %H:%M') if m.fecha else '',
            m.elemento.nombre if m.elemento else '',
            m.tipo.upper(),
            str(m.cantidad),
            m.observacion or '',
            m.usuario.nombre if m.usuario else ''
        ])

    tabla = Table(encabezado + filas, colWidths=[95, 120, 55, 55, 120, 95])
    tabla.setStyle(estilo_tabla())

    for i, m in enumerate(movimientos_lista, start=1):
        color = colors.HexColor('#1a7a3a') if m.tipo == 'entrada' else colors.red
        tabla.setStyle(TableStyle([
            ('TEXTCOLOR', (2, i), (2, i), color),
            ('FONTNAME',  (2, i), (2, i), 'Helvetica-Bold'),
        ]))

    bloques.append(tabla)
    doc.build(bloques)
    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=reporte_movimientos.pdf'
    return response


# ─── PDF VENTAS ───────────────────────────────────────────────────────────────

@reporte_bp.route('/reportes/ventas/pdf')
@login_required
@rol_requerido('admin')
def ventas_pdf():
    cliente_id  = request.args.get('cliente_id', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')

    query = Venta.query
    if cliente_id:
        query = query.filter_by(cliente_id=cliente_id)

    dt_desde, dt_hasta = parsear_fechas(fecha_desde, fecha_hasta)
    if dt_desde:
        query = query.filter(Venta.fecha >= dt_desde)
    if dt_hasta:
        query = query.filter(Venta.fecha <= dt_hasta)

    ventas_lista  = query.order_by(Venta.fecha.desc()).all()
    total_general = sum(float(v.total) for v in ventas_lista)

    buffer  = io.BytesIO()
    doc     = SimpleDocTemplate(buffer, pagesize=A4,
                                topMargin=40, bottomMargin=40,
                                leftMargin=40, rightMargin=40)
    styles  = getSampleStyleSheet()
    bloques = []

    bloques.append(Paragraph("El Cafetero de Nufi", styles['Title']))
    bloques.append(Paragraph("Reporte de Ventas", styles['Heading2']))
    bloques.append(Spacer(1, 6))

    fecha_generado = datetime.now().strftime('%d/%m/%Y %H:%M')
    bloques.append(Paragraph(f"Generado: {fecha_generado}", styles['Normal']))
    if fecha_desde:
        bloques.append(Paragraph(f"Desde: {fecha_desde}", styles['Normal']))
    if fecha_hasta:
        bloques.append(Paragraph(f"Hasta: {fecha_hasta}", styles['Normal']))
    bloques.append(Paragraph(
        f"Total facturas: {len(ventas_lista)}  |  Total recaudado: ${total_general:,.2f}",
        styles['Normal']
    ))
    bloques.append(Spacer(1, 12))

    encabezado = [['Factura #', 'Cliente', 'Productos', 'Total', 'Fecha']]
    filas = []
    for v in ventas_lista:
        productos_str = ', '.join(
            f"{d.producto.nombre} x{int(d.cantidad)}" for d in v.detalles
        )
        filas.append([
            f"#{v.id}",
            v.cliente.nombre if v.cliente else '',
            productos_str,
            f"${float(v.total):,.2f}",
            v.fecha.strftime('%d/%m/%Y %H:%M') if v.fecha else ''
        ])

    tabla = Table(encabezado + filas, colWidths=[55, 100, 185, 75, 85])
    tabla.setStyle(estilo_tabla())
    bloques.append(tabla)

    bloques.append(Spacer(1, 12))
    bloques.append(Paragraph(
        f"<b>Total general: ${total_general:,.2f}</b>",
        styles['Normal']
    ))

    doc.build(bloques)
    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=reporte_ventas.pdf'
    return response
