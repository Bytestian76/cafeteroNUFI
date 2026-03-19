# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CafeteroNUFI is a Flask web application for managing a coffee business — inventory, products, sales, and reporting.

## Development Setup

```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (edit .env with your DB credentials)
# DATABASE_URL=mysql+pymysql://user:password@localhost/cafetero_db

# Run database migrations
flask db upgrade

# Start the app
python run.py
```

App runs at `http://localhost:5000`.

## Common Commands

```bash
# Run the app
python run.py

# Database migrations
flask db migrate -m "description"
flask db upgrade
flask db downgrade

# Open Flask shell (for manual DB operations)
flask shell
```

## Architecture

The app uses the **Flask Application Factory** pattern with **Blueprints**:

- `app/__init__.py` — creates the Flask app, registers blueprints, initializes extensions (SQLAlchemy, Flask-Login, Bcrypt, Migrate, WTF)
- `config.py` — reads `SECRET_KEY` and `DATABASE_URL` from `.env`
- `run.py` — entry point, calls `create_app()`

### Blueprints (each in `app/controllers/`)

| Blueprint | URL prefix | Purpose |
|-----------|------------|---------|
| `auth_bp` | `/` | Login, logout, dashboard, user management |
| `inventario_bp` | `/inventario` | Inventory CRUD |
| `movimiento_bp` | `/movimientos` | Stock entry/exit log |
| `producto_bp` | `/productos` | Product catalog |
| `venta_bp` | `/ventas` | Sales invoicing and client management |
| `reporte_bp` | `/reportes` | PDF report generation |

### Models (`app/models/`)

- `usuario.py` — `Usuario` (roles: `admin`, `operario`, `consultor`)
- `inventario.py` — `ElementoInventario` (categories: `insumo`, `maquinaria`, `herramienta`, `material`)
- `movimiento.py` — `Movimiento` (types: `entrada`, `salida`)
- `producto.py` — `Producto`
- `venta.py` — `Cliente`, `Venta`, `DetalleVenta`

### Templates (`app/views/`)

Jinja2 templates extending `base.html`. Organized in subdirectories matching each blueprint. Bootstrap 5 is loaded via CDN.

### Access Control

- `@login_required` from Flask-Login on most routes
- `@admin_required` custom decorator in `app/utils/decorators.py` restricts routes to `rol == 'admin'`

### PDF Reports

Generated using ReportLab in `app/controllers/reporte_controller.py`. Reports cover inventory status, movement history, and sales summaries.

### Database

MySQL via PyMySQL. Schema managed with Flask-Migrate (Alembic). SQL dump available at `database/cafetero_db.sql`.

## Environment Variables (`.env`)

```
FLASK_SECRET_KEY=<long random string>
DATABASE_URL=mysql+pymysql://root:password@localhost/cafetero_db
FLASK_ENV=development
```
## Instrucciones de comportamiento

- Responde siempre en español
- Sé conciso y directo. No des explicaciones que no te pedí. Si quiero detalles, yo los pido.
- Antes de hacer cualquiera de estas acciones, pídeme permiso explícito:
  - Eliminar o borrar código existente
  - Hacer commits
  - Modificar la base de datos (ALTER, DROP, DELETE masivo)
  - Cualquier cambio irreversible o estructural importante

## Estilo de comentarios en el código

- Comenta por funciones/bloques, no línea por línea
- Los comentarios deben ser cortos y claros
- Si una función se conecta con otra, indica en el comentario el nombre y línea de la función relacionada
- Ejemplo de comentario aceptable:
  # Calcula el total de la venta incluyendo IVA → conectado con aplicar_descuento() línea 87