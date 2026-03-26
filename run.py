# run.py — Punto de entrada de la aplicación.
# Llama a create_app() definida en app/__init__.py y arranca el servidor.
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)