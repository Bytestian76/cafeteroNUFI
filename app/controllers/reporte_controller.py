from flask import Blueprint, render_template, request, make_response
from flask_login import login_required
from app.models.inventario import ElementoInventario
from app.models.movimiento import Movimiento
from app.models.venta import Venta, Cliente
from app.utils.decorators import rol_requerido

# ─── ReportLab ────────────────────────────────────────────────────────────────
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

reporte_bp = Blueprint('reportes', __name__)


# ─── HELPER: estilo base de tabla ─────────────────────────────────────────────

def estilo_tabla():
    return TableStyle([
        # Encabezado verde cafetero
        ('BACKGROUND',   (0, 0), (-1, 0),  colors.HexColor('#2c7a4b')),
        ('TEXTCOLOR',    (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',     (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, 0),  10),
        # Filas alternas
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f2f2')]),
        ('FONTSIZE',     (0, 1), (-1, -1),  9),
        # Bordes
        ('GRID',         (0, 0), (-1, -1),  0.4, colors.HexColor('#cccccc')),
        ('TOPPADDING',   (0, 0), (-1, -1),  6),
        ('BOTTOMPADDING',(0, 0), (-1, -1),  6),
        ('LEFTPADDING',  (0, 0), (-1, -1),  8),
    ])


# ─── REPORTE DE INVENTARIO (RF18) ─────────────────────────────────────────────

@reporte_bp.route('/reportes/inventario')
@login_required
@rol_requerido('admin', 'consultor')
def inventario():
    categoria = request.args.get('categoria', '')
    alerta    = request.args.get('alerta', '')

    query = ElementoInventario.query.filter_by(activo=True)
    if categoria:
        query = query.filter_by(categoria=categoria)

    elementos = query.order_by(ElementoInventario.nombre).all()
    if alerta == '1':
        elementos = [e for e in elementos if e.tiene_alerta()]

    con_escasez = sum(1 for e in elementos if e.tiene_alerta())
    sin_escasez = len(elementos) - con_escasez

    return render_template('reportes/inventario.html',
                        elementos=elementos,
                        categoria=categoria,
                        alerta=alerta,
                        con_escasez=con_escasez,
                        sin_escasez=sin_escasez)


# ─── REPORTE DE INVENTARIO EN PDF ─────────────────────────────────────────────

@reporte_bp.route('/reportes/inventario/pdf')
@login_required
@rol_requerido('admin', 'consultor')
def inventario_pdf():
    categoria = request.args.get('categoria', '')
    alerta    = request.args.get('alerta', '')

    # 1. Misma consulta que la vista normal
    query = ElementoInventario.query.filter_by(activo=True)
    if categoria:
        query = query.filter_by(categoria=categoria)

    elementos = query.order_by(ElementoInventario.nombre).all()
    if alerta == '1':
        elementos = [e for e in elementos if e.tiene_alerta()]

    con_escasez = sum(1 for e in elementos if e.tiene_alerta())

    # 2. Crear PDF en memoria
    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=40, bottomMargin=40,
                            leftMargin=40, rightMargin=40)
    styles  = getSampleStyleSheet()
    bloques = []

    # 3. Título y subtítulo
    bloques.append(Paragraph("El Cafetero de Nufi", styles['Title']))
    bloques.append(Paragraph("Reporte de Inventario", styles['Heading2']))
    bloques.append(Spacer(1, 6))

    # Filtros aplicados
    if categoria:
        bloques.append(Paragraph(f"Categoría: {categoria}", styles['Normal']))
    if alerta == '1':
        bloques.append(Paragraph("Filtro: Solo elementos con alerta de escasez", styles['Normal']))
    bloques.append(Paragraph(f"Total elementos: {len(elementos)}  |  Con escasez: {con_escasez}", styles['Normal']))
    bloques.append(Spacer(1, 12))

    # 4. Tabla de datos
    encabezado = [['Nombre', 'Categoría', 'Unidad', 'Stock Actual', 'Stock Mínimo', 'Estado']]
    filas = []
    for e in elementos:
        estado = '⚠ Escasez' if e.tiene_alerta() else '✔ OK'
        filas.append([
            e.nombre,
            e.categoria,
            e.unidad_medida,
            str(e.stock_actual),
            str(e.stock_minimo),
            estado
        ])

    tabla = Table(encabezado + filas, colWidths=[140, 90, 70, 70, 70, 60])
    tabla.setStyle(estilo_tabla())

    # Colorear rojo las filas con alerta
    for i, e in enumerate(elementos, start=1):
        if e.tiene_alerta():
            tabla.setStyle(TableStyle([
                ('TEXTCOLOR', (5, i), (5, i), colors.red),
                ('FONTNAME',  (5, i), (5, i), 'Helvetica-Bold'),
            ]))

    bloques.append(tabla)

    # 5. Construir y enviar
    doc.build(bloques)
    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=reporte_inventario.pdf'
    return response


# ─── REPORTE DE MOVIMIENTOS (RF19) ────────────────────────────────────────────

@reporte_bp.route('/reportes/movimientos')
@login_required
@rol_requerido('admin', 'consultor')
def movimientos():
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
        query = query.filter(Movimiento.fecha <= fecha_hasta + ' 23:59:59')

    movimientos_lista = query.order_by(Movimiento.fecha.desc()).all()
    elementos         = ElementoInventario.query.filter_by(activo=True).order_by(ElementoInventario.nombre).all()

    total_entradas = sum(float(m.cantidad) for m in movimientos_lista if m.tipo == 'entrada')
    total_salidas  = sum(float(m.cantidad) for m in movimientos_lista if m.tipo == 'salida')

    return render_template('reportes/movimientos.html',
                        movimientos=movimientos_lista,
                        elementos=elementos,
                        filtros={'elemento_id': elemento_id, 'tipo': tipo,
                                    'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta},
                        total_entradas=total_entradas,
                        total_salidas=total_salidas)


# ─── REPORTE DE MOVIMIENTOS EN PDF ────────────────────────────────────────────

@reporte_bp.route('/reportes/movimientos/pdf')
@login_required
@rol_requerido('admin', 'consultor')
def movimientos_pdf():
    elemento_id = request.args.get('elemento_id', '')
    tipo        = request.args.get('tipo', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')

    # 1. Misma consulta que la vista normal
    query = Movimiento.query
    if elemento_id:
        query = query.filter_by(elemento_id=elemento_id)
    if tipo:
        query = query.filter_by(tipo=tipo)
    if fecha_desde:
        query = query.filter(Movimiento.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Movimiento.fecha <= fecha_hasta + ' 23:59:59')

    movimientos_lista = query.order_by(Movimiento.fecha.desc()).all()
    total_entradas = sum(float(m.cantidad) for m in movimientos_lista if m.tipo == 'entrada')
    total_salidas  = sum(float(m.cantidad) for m in movimientos_lista if m.tipo == 'salida')

    # 2. Crear PDF en memoria
    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=40, bottomMargin=40,
                            leftMargin=40, rightMargin=40)
    styles  = getSampleStyleSheet()
    bloques = []

    # 3. Título
    bloques.append(Paragraph("El Cafetero de Nufi", styles['Title']))
    bloques.append(Paragraph("Reporte de Movimientos", styles['Heading2']))
    bloques.append(Spacer(1, 6))

    # Filtros aplicados
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

    # 4. Tabla
    encabezado = [['Fecha', 'Elemento', 'Tipo', 'Cantidad', 'Motivo', 'Usuario']]
    filas = []
    for m in movimientos_lista:
        filas.append([
            m.fecha.strftime('%d/%m/%Y %H:%M') if m.fecha else '',
            m.elemento.nombre if m.elemento else '',
            m.tipo.upper(),
            str(m.cantidad),
            m.motivo or '',
            m.usuario.nombre if m.usuario else ''
        ])

    tabla = Table(encabezado + filas, colWidths=[95, 120, 55, 55, 120, 95])
    tabla.setStyle(estilo_tabla())

    # Colorear tipo: entradas verde, salidas rojo
    for i, m in enumerate(movimientos_lista, start=1):
        color = colors.HexColor('#1a7a3a') if m.tipo == 'entrada' else colors.red
        tabla.setStyle(TableStyle([
            ('TEXTCOLOR', (2, i), (2, i), color),
            ('FONTNAME',  (2, i), (2, i), 'Helvetica-Bold'),
        ]))

    bloques.append(tabla)

    # 5. Construir y enviar
    doc.build(bloques)
    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=reporte_movimientos.pdf'
    return response


# ─── REPORTE DE VENTAS (RF17) ─────────────────────────────────────────────────

@reporte_bp.route('/reportes/ventas')
@login_required
@rol_requerido('admin', 'consultor')
def ventas():
    cliente_id  = request.args.get('cliente_id', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')

    query = Venta.query
    if cliente_id:
        query = query.filter_by(cliente_id=cliente_id)
    if fecha_desde:
        query = query.filter(Venta.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Venta.fecha <= fecha_hasta + ' 23:59:59')

    ventas_lista  = query.order_by(Venta.fecha.desc()).all()
    clientes      = Cliente.query.order_by(Cliente.nombre).all()
    total_general = sum(float(v.total) for v in ventas_lista)

    return render_template('reportes/ventas.html',
                        ventas=ventas_lista,
                        clientes=clientes,
                        filtros={'cliente_id': cliente_id,
                                    'fecha_desde': fecha_desde,
                                    'fecha_hasta': fecha_hasta},
                        total_general=total_general)