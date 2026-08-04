from src.database.connection import SessionLocal, init_db
from src.services.auth_service import garantir_perfis_padrao

import src.database.models.cadastros
import src.database.models.producao
import src.database.models.core
import src.database.models.estoque
import src.database.models.vendas

def main() -> None:
    init_db()
    
    db = SessionLocal()
    try:
        garantir_perfis_padrao(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    
    print("Banco inicializado e perfis padrão cadastrados.")


if __name__ == "__main__":
    main()