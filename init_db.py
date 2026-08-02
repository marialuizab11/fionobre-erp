from src.database.connection import SessionLocal, init_db
from src.services.auth_service import garantir_perfis_padrao


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
