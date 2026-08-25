import random
from datetime import datetime, timedelta
from decimal import Decimal

from src.database.connection import SessionLocal, init_db
from src.database.models.cadastros import Cliente, Item
from src.database.models.estoque import *
from src.database.models.compras import *
from src.database.models.producao import *
from src.database.models.logistica import *
from src.database.models.usuarios import Usuario
from src.database.models.vendas import PedidoVenda, ItemVenda, PedidoVendaHistorico
from src.database.models.financeiro import LancamentoFinanceiro

try:
    from src.database.models.cadastros import Fornecedor
except ImportError:
    from src.database.models.compras import Fornecedor

from src.database.models.compras import PedidoCompra, ItemCompra


def gerar_dados_teste():
    db = SessionLocal()
    try:
        print("Iniciando o povoamento do banco de dados (Vendas, Compras, Estoque e Financeiro)...")
        init_db()

        usuario = db.query(Usuario).first()
        if not usuario:
            usuario = Usuario(nome="Admin Teste", email="admin@fionobre.com", ativo=True)
            db.add(usuario)
            db.commit()
            db.refresh(usuario)

        print("Gerando Clientes e Fornecedores...")
        clientes = []
        for i in range(1, 16):
            c = Cliente(
                razao_social=f"Cliente Empresa {i} LTDA",
                cnpj_cpf=f"{random.randint(10,99)}.000.000/0001-{random.randint(10,99)}",
                email=f"contato{i}@empresa.com",
                cidade=random.choice(["Recife", "São Paulo", "Caruaru", "Campinas", "Belo Horizonte"]),
                uf=random.choice(["PE", "SP", "PE", "SP", "MG"])
            )
            db.add(c)
            clientes.append(c)

        fornecedores = []
        for i in range(1, 6):
            f = Fornecedor(
                razao_social=f"Indústria Fornecedora {i} S.A",
                cnpj_cpf=f"{random.randint(10,99)}.111.222/0001-{random.randint(10,99)}",
                email=f"vendas{i}@fornecedor.com",
                cidade=random.choice(["Blumenau", "Joinville", "Americana"]),
                uf=random.choice(["SC", "SC", "SP"])
            )
            db.add(f)
            fornecedores.append(f)
            
        db.commit()

        print("Gerando Itens de Estoque...")
        catalogo = [
            ("Fio de Algodão Cru 20/1", "PRODUTO_ACABADO", 15.50, 8.00),
            ("Fio de Poliéster 30/1", "PRODUTO_ACABADO", 18.20, 10.00),
            ("Fio Tinto Preto 24/1", "PRODUTO_ACABADO", 22.00, 12.50),
            ("Fio Mescla Cinza", "PRODUTO_ACABADO", 25.00, 14.00),
            ("Malha Tubular Algodão", "PRODUTO_ACABADO", 35.90, 20.00),
            ("Fardo Algodão Pluma", "MATERIA_PRIMA", 0.00, 12.00),
            ("Fibra Poliéster Fio", "MATERIA_PRIMA", 0.00, 9.50),
            ("Corante Têxtil Preto", "MATERIA_PRIMA", 0.00, 45.00)
        ]
        
        itens_db = []
        materias_primas = []
        produtos_acabados = []
        
        for desc, tipo, preco, custo in catalogo:
            item = Item(
                descricao=desc,
                tipo_item=tipo,
                unidade_medida="KG",
                preco_venda=Decimal(str(preco)),
                custo_medio=Decimal(str(custo)),
                saldo_estoque=Decimal(str(random.randint(500, 2000))),
                estoque_minimo=Decimal("150.00")
            )
            db.add(item)
            itens_db.append(item)
            if tipo == "PRODUTO_ACABADO":
                produtos_acabados.append(item)
            else:
                materias_primas.append(item)
                
        db.commit()

        hoje = datetime.now()
        status_vendas = ["Confirmado", "Concluído", "Orcamento", "Cancelado"]
        status_compras = ["Recebido", "Confirmado", "Criado", "Cancelado"]

        print("Gerando Pedidos de Venda e Contas a Receber...")
        for _ in range(80):
            cliente = random.choice(clientes)
            status = random.choices(status_vendas, weights=[40, 30, 20, 10])[0]
            dias_atras = random.randint(0, 90)
            data_pedido = hoje - timedelta(days=dias_atras)

            pedido_venda = PedidoVenda(
                id_cliente=cliente.id_cliente,
                id_usuario=usuario.id_usuario,
                status_venda=status,
                data_venda=data_pedido,
                valor_total_pedido=Decimal("0.00")
            )
            db.add(pedido_venda)
            db.flush()

            qtd_itens = random.randint(1, 3)
            itens_escolhidos = random.sample(produtos_acabados, k=qtd_itens)
            
            valor_total_v = Decimal("0.00")
            for item in itens_escolhidos:
                qtd = Decimal(str(random.randint(10, 100)))
                vlr_un = item.preco_venda
                valor_total_v += qtd * vlr_un
                
                db.add(ItemVenda(
                    id_pedido_venda=pedido_venda.id_pedido_venda,
                    id_item=item.id_item,
                    quantidade_vendida=qtd,
                    valor_unitario=vlr_un
                ))
            
            pedido_venda.valor_total_pedido = valor_total_v

            db.add(PedidoVendaHistorico(
                id_pedido_venda=pedido_venda.id_pedido_venda,
                id_usuario=usuario.id_usuario,
                nome_usuario=usuario.nome,
                status_novo=status,
                justificativa="Gerado via Seeder",
                data_hora=data_pedido
            ))

            if status in ["Confirmado", "Concluído"]:
                eh_a_vista = random.random() < 0.3
                prazo = 0 if eh_a_vista else random.choice([30, 60, 90])
                vencimento = (data_pedido + timedelta(days=prazo)).date()
                status_pag = "Pago" if eh_a_vista else ("Pago" if vencimento < hoje.date() and random.random() > 0.4 else "Pendente")

                db.add(LancamentoFinanceiro(
                    id_pedido_venda=pedido_venda.id_pedido_venda,
                    valor=valor_total_v,
                    data_vencimento=vencimento,
                    tipo_lancamento="CONTA_A_RECEBER",
                    origem_lancamento="VENDA",
                    status_pagamento=status_pag,
                ))

        print("Gerando Pedidos de Compra e Contas a Pagar...")
        for _ in range(30):
            fornecedor = random.choice(fornecedores)
            status_c = random.choices(status_compras, weights=[50, 20, 20, 10])[0]
            dias_atras = random.randint(0, 90)
            data_compra = hoje - timedelta(days=dias_atras)

            pedido_compra = PedidoCompra(
                id_fornecedor=fornecedor.id_fornecedor,
                id_usuario=usuario.id_usuario,
                status_compra=status_c,
                data_pedido=data_compra,
                valor_total_pedido=Decimal("0.00")
            )
            db.add(pedido_compra)
            db.flush()

            qtd_itens_c = random.randint(1, 2)
            itens_compra_escolhidos = random.sample(materias_primas, k=qtd_itens_c)
            
            valor_total_c = Decimal("0.00")
            for item in itens_compra_escolhidos:
                qtd = Decimal(str(random.randint(100, 500)))
                vlr_un = item.custo_medio
                valor_total_c += qtd * vlr_un
                
                db.add(ItemCompra(
                    id_pedido_compra=pedido_compra.id_pedido_compra,
                    id_item=item.id_item,
                    quantidade_comprada=qtd,
                    custo_unitario=vlr_un
                ))
            
            pedido_compra.valor_total_pedido = valor_total_c

            if status_c in ["Confirmado", "Recebido"]:
                prazo_pgto = random.choice([15, 30, 45])
                vencimento_pgto = (data_compra + timedelta(days=prazo_pgto)).date()
                status_pag_c = "Pago" if vencimento_pgto < hoje.date() and random.random() > 0.2 else "Pendente"

                db.add(LancamentoFinanceiro(
                    valor=valor_total_c,
                    data_vencimento=vencimento_pgto,
                    tipo_lancamento="CONTA_A_PAGAR",
                    origem_lancamento="COMPRA",
                    status_pagamento=status_pag_c,
                ))

        db.commit()
        print("\nBase de dados consolidada com sucesso!")
        print("-> Clientes, Fornecedores e Itens gerados.")
        print("-> Pedidos de Venda e Compras injetados no historico (ultimos 90 dias).")
        print("-> Contas a Pagar e a Receber provisionadas para a Visao Financeira.")

    except Exception as e:
        db.rollback()
        print(f"Erro ao popular banco: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    gerar_dados_teste()