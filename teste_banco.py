import os
import sys

# Descobre o caminho absoluto do diretório onde este script está (fionobre-erp)
raiz_projeto = os.path.dirname(os.path.abspath(__file__))

# Força a inclusão da raiz do projeto e da pasta src no início do path do Python
if raiz_projeto not in sys.path:
    sys.path.insert(0, raiz_projeto)
if os.path.join(raiz_projeto, "src") not in sys.path:
    sys.path.insert(0, os.path.join(raiz_projeto, "src"))

try:
    from src.database.connection import init_db
    print("Módulos importados com sucesso!")
except ModuleNotFoundError as e:
    print(f"\n[ERRO DE IMPORTAÇÃO]: {e}")
    print("Caminhos verificados pelo Python atual:")
    for p in sys.path[:3]:
        print(f" -> {p}")
    sys.exit(1)

if __name__ == "__main__":
    print("Conectando ao PostgreSQL local e gerando as tabelas da Frente 2...")
    try:
        init_db()
        print("Sucesso! As tabelas foram geradas com êxito no banco de dados.")
    except Exception as e:
        print(f"Ops, ocorreu um erro na criação do banco: {e}")