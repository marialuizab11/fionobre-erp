from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import DATABASE_URL
from src.database.models.base import Base

# 1. Cria o motor de conexão com o PostgreSQL usando a URL do seu .env
engine = create_engine(DATABASE_URL, echo=True)

# 2. Cria a fábrica de sessões para executar os comandos SQL
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Lê todas as tabelas importadas no pacote de models 
    e as cria automaticamente no PostgreSQL local.
    """
    # Garante que todos os modelos estejam registrados no metadata antes do create_all.
    import src.database.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

def get_db():
    """
    Gerenciador de conexão seguro (abre e fecha a sessão)
    para ser usado nas regras de negócio (Services).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
