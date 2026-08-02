import os
from dotenv import load_dotenv
from sqlalchemy.engine import URL

# Carrega as variáveis do arquivo .env localizado na raiz do projeto
load_dotenv()

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "fionobre_db")

# E-mails separados por vírgula que recebem o perfil Administrador no primeiro login.
ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "").split(",")
    if email.strip()
}

# Usa URL.create para aceitar senhas com caracteres especiais sem expô-las.
DATABASE_URL = URL.create(
    "postgresql+psycopg2",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)
