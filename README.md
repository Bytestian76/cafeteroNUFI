#Hola chamitos, este es el paso a paso para que funcione el código de manera local en cada pc

#Paso 1
git clone https://github.com/Bytestian76/cafeteroNUFI.git
cd cafeteroNUFI

#Paso 2
python -m venv .venv
.venv\Scripts\activate

#Paso 3
pip install -r requirements.txt


#Paso 4
FLASK_SECRET_KEY=cualquier_clave_secreta_larga
DATABASE_URL=mysql+pymysql://usuario:contraseña@localhost/cafetero_db
FLASK_ENV=development

#Paso 5
CREATE DATABASE cafetero_db;

#Paso 6
flask db upgrade

#Paso 7
flask shell

from app import bcrypt, db
from app.models.usuario import Usuario

admin = Usuario(
    nombre='Administrador',
    email='admin@nufi.com',
    password_hash=bcrypt.generate_password_hash('admin123').decode('utf-8'),
    rol='admin'
)
db.session.add(admin)
db.session.commit()
exit()

#Paso 8 
python run.py
#Casino-Roulette
# Casino-Roulette
