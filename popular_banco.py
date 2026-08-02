import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.connection import SessionLocal, init_db

from src.database.models.cadastros import Cliente, Item
from src.database.models.core import MovimentacaoEstoque
from src.database.models.logistica import Entrega
from src.database.models.vendas import PedidoVenda, ItemVenda
from src.database.models.financeiro import LancamentoFinanceiro

def popular_dados_iniciais():
    print("Sincronizando modelos com o banco de dados...")
    init_db() 
    
    db = SessionLocal()
    
    try:
        if db.query(Cliente).count() == 0:
            print("Inserindo Clientes...")
            clientes = [
                Cliente(
                    razao_social="Indústria Têxtil Alpha Ltda", 
                    cnpj_cpf="12.345.678/0001-90", 
                    cidade="Caruaru", 
                    uf="PE", 
                    cep="55000-000", 
                    rua="Av. Principal", 
                    numero="100", 
                    bairro="Centro", 
                    email="contato@alpha.com.br", 
                    telefone="(81) 99999-1111"
                ),
                Cliente(
                    razao_social="Confecções Beta", 
                    cnpj_cpf="98.765.432/0001-10", 
                    cidade="Toritama", 
                    uf="PE", 
                    cep="55125-000", 
                    rua="Rua do Comércio", 
                    numero="250", 
                    bairro="Polo", 
                    email="compras@beta.com.br", 
                    telefone="(81) 98888-2222"
                ),
                Cliente(
                    razao_social="Malharia Gama", 
                    cnpj_cpf="45.678.912/0001-34", 
                    cidade="Santa Cruz do Capibaribe", 
                    uf="PE", 
                    cep="55190-000", 
                    rua="Moda Center", 
                    numero="Setor Azul", 
                    bairro="Nova Santa Cruz", 
                    email="financeiro@gama.com.br", 
                    telefone="(81) 97777-3333"
                )
            ]
            db.add_all(clientes)
            print("-> Clientes cadastrados com sucesso.")
        else:
            print("-> Clientes já existem no banco.")

        if db.query(Item).count() == 0:
            print("Inserindo Itens e Insumos...")
            itens = [
                Item(
                    descricao="Bobina de Fio de Algodão Cru 500m", 
                    tipo_item="Materia-Prima", 
                    unidade_medida="Un", 
                    saldo_estoque=150.0, 
                    estoque_minimo=50.0,
                    custo_medio=45.00, 
                    preco_venda=80.00
                ),
                Item(
                    descricao="Carretel de Fio Sintético Preto", 
                    tipo_item="Materia-Prima", 
                    unidade_medida="Un", 
                    saldo_estoque=300.0, 
                    estoque_minimo=100.0,
                    custo_medio=15.00, 
                    preco_venda=30.00
                ),
                Item(
                    descricao="Fio de Poliéster Branco 1000m", 
                    tipo_item="Materia-Prima", 
                    unidade_medida="Un", 
                    saldo_estoque=500.0, 
                    estoque_minimo=150.0,
                    custo_medio=25.00, 
                    preco_venda=45.00
                ),
                Item(
                    descricao="Tecido Malha Penteada Azul", 
                    tipo_item="Materia-Prima", 
                    unidade_medida="Kg", 
                    saldo_estoque=200.0, 
                    estoque_minimo=50.0,
                    custo_medio=35.00, 
                    preco_venda=65.00
                )
            ]
            db.add_all(itens)
            print("-> Itens e estoque inicial cadastrados com sucesso.")
        else:
            print("-> Itens já existem no banco.")

        db.commit()
        print("\nSucesso! Banco populado e pronto para os testes.")
        
    except Exception as e:
        db.rollback()
        print(f"\nErro ao popular banco: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    popular_dados_iniciais()