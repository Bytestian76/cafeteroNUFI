# reporte_controller.py — Generación de reportes PDF globales con ReportLab.
# Rutas:
#   /reportes/inventario/pdf  → tabla de elementos con estado de stock
#   /reportes/movimientos/pdf → historial de movimientos con filtros
#   /reportes/ventas/pdf      → resumen de facturas con total general
# Todos devuelven un PDF inline para visualizar en el navegador.
from flask import Blueprint, make_response, request
from flask_login import login_required
from app.models.inventario import ElementoInventario
from app.models.movimiento import Movimiento
from app.models.venta import Venta, Cliente
from datetime import datetime, timedelta

import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

reporte_bp = Blueprint('reportes', __name__)


# ─── HELPER: convertir fechas string a datetime ───────────────────────────────
# fecha_hasta se extiende al final del día (23:59:59) para incluir todo el día.

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
# Encabezado verde oscuro, filas alternas blanco/gris, grilla ligera.
# Se usa en los tres reportes PDF.

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
# Filtros opcionales: categoría y alerta (solo elementos en escasez).
# Las filas con escasez se colorean en rojo en la columna "Estado".

@reporte_bp.route('/reportes/inventario/pdf')
@login_required
def inventario_pdf():
    categoria = request.args.get('categoria', '')
    alerta    = request.args.get('alerta', '')

    query = ElementoInventario.query.filter_by(activo=True)
    if categoria:
        query = query.filter_by(categoria=categoria)

    elementos = query.order_by(ElementoInventario.nombre).all()
    if alerta == '1':
        elementos = [e for e in elementos if e.tiene_alerta]

    con_escasez = sum(1 for e in elementos if e.tiene_alerta)

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
        estado = 'Escasez' if e.tiene_alerta else 'OK'
        filas.append([
            e.nombre, e.categoria, e.unidad_medida,
            str(e.stock_actual), str(e.stock_minimo), estado
        ])

    tabla = Table(encabezado + filas, colWidths=[140, 90, 70, 70, 70, 60])
    tabla.setStyle(estilo_tabla())

    # Colorear en rojo la celda "Estado" de los elementos en escasez
    for i, e in enumerate(elementos, start=1):
        if e.tiene_alerta:
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
# Filtros: elemento, tipo (entrada/salida), rango de fechas.
# Las entradas se colorean en verde y las salidas en rojo en la columna "Tipo".

@reporte_bp.route('/reportes/movimientos/pdf')
@login_required
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

    # Verde para entradas, rojo para salidas en la columna "Tipo"
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
# Filtros: cliente y rango de fechas.
# Incluye todas las ventas (incluso anuladas) y muestra el total general al final.

@reporte_bp.route('/reportes/ventas/pdf')
@login_required
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

    # Estilos de celda con word-wrap automático
    s_celda = ParagraphStyle('vc', fontSize=9,  leading=13, wordWrap='LTR')
    s_prod  = ParagraphStyle('vp', fontSize=8,  leading=12, wordWrap='LTR')
    s_th    = ParagraphStyle('vth', fontSize=10, leading=14, fontName='Helvetica-Bold',
                             textColor=colors.white, alignment=TA_CENTER)

    encabezado = [[
        Paragraph('Factura #', s_th),
        Paragraph('Cliente',   s_th),
        Paragraph('Productos', s_th),
        Paragraph('Total',     s_th),
        Paragraph('Fecha',     s_th),
    ]]
    filas = []
    for v in ventas_lista:
        # Cada producto en su propia línea dentro de la celda
        productos_html = '<br/>'.join(
            f"• {d.producto.nombre if d.producto else '(eliminado)'} × {int(d.cantidad)}"
            for d in v.detalles
        )
        filas.append([
            Paragraph(f"#{v.id}",                                          s_celda),
            Paragraph(v.cliente.nombre if v.cliente else '',               s_celda),
            Paragraph(productos_html,                                      s_prod),
            Paragraph(f"${float(v.total):,.2f}",                          s_celda),
            Paragraph(v.fecha.strftime('%d/%m/%Y %H:%M') if v.fecha else '', s_celda),
        ])

    col_w = [48, 105, 190, 78, 94]   # suma = 515 pt = ancho útil A4 con márgenes 40+40
    tabla = Table(encabezado + filas, colWidths=col_w, repeatRows=1)
    estilo = estilo_tabla()
    estilo.add('VALIGN',      (0, 0), (-1, -1), 'TOP')
    estilo.add('ALIGN',       (0, 0), (-1, -1), 'CENTER')
    estilo.add('ALIGN',       (2, 1), (2, -1),  'LEFT')   # productos: lista alineada a la izquierda
    tabla.setStyle(estilo)
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
