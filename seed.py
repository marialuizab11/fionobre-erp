import random
from datetime import datetime, timedelta
from decimal import Decimal

from src.database.connection import SessionLocal, init_db
from src.database.models.cadastros import Cliente, Item
from src.database.models.usuarios import Usuario
from src.database.models.vendas import PedidoVenda, ItemVenda, PedidoVendaHistorico
from src.database.models.financeiro import LancamentoFinanceiro
from src.database.models.estoque import * 

def gerar_dados_teste():
    db = SessionLocal()
    try:
        print("Criando tabelas e limpando dados antigos (se necessário)...")
        init_db()

        # 1. Criar Usuário Teste (se não existir)
        usuario = db.query(Usuario).first()
        if not usuario:
            usuario = Usuario(nome="Admin Teste", email="admin@fionobre.com", ativo=True)
            db.add(usuario)
            db.commit()
            db.refresh(usuario)

        # 2. Criar Clientes
        print("Gerando Clientes...")
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
        db.commit()

        # 3. Criar Itens (Produtos Acabados)
        print("Gerando Itens de Estoque...")
        produtos = [
            ("Fio de Algodão Cru 20/1", 15.50, 8.00),
            ("Fio de Poliéster 30/1", 18.20, 10.00),
            ("Fio Tinto Preto 24/1", 22.00, 12.50),
            ("Fio Mescla Cinza", 25.00, 14.00),
            ("Malha Tubular Algodão", 35.90, 20.00),
            ("Fio Cardado Branco", 14.00, 7.50),
            ("Fio Penteado Premium", 28.50, 15.00)
        ]
        
        itens_db = []
        for desc, preco, custo in produtos:
            item = Item(
                descricao=desc,
                tipo_item="PRODUTO_ACABADO",
                unidade_medida="KG",
                preco_venda=Decimal(str(preco)),
                custo_medio=Decimal(str(custo)),
                saldo_estoque=Decimal(str(random.randint(500, 2000))),
                estoque_minimo=Decimal("100.00")
            )
            db.add(item)
            itens_db.append(item)
        db.commit()

        # 4. Gerar Pedidos de Venda e Financeiro (Passado e Futuro)
        print("Gerando Pedidos e Lançamentos Financeiros...")
        status_opcoes = ["Confirmado", "Concluído", "Orcamento", "Cancelado"]
        
        hoje = datetime.now()
        
        for _ in range(80): # Gerar 80 pedidos aleatórios
            cliente = random.choice(clientes)
            status = random.choices(status_opcoes, weights=[40, 30, 20, 10])[0]
            
            # Data retroativa entre 90 dias atrás e hoje
            dias_atras = random.randint(0, 90)
            data_pedido = hoje - timedelta(days=dias_atras)

            pedido = PedidoVenda(
                id_cliente=cliente.id_cliente,
                id_usuario=usuario.id_usuario,
                status_venda=status,
                data_venda=data_pedido,
                valor_total_pedido=Decimal("0.00")
            )
            db.add(pedido)
            db.flush()

            # Adicionar itens ao pedido
            qtd_itens = random.randint(1, 4)
            itens_escolhidos = random.sample(itens_db, k=qtd_itens)
            
            valor_total = Decimal("0.00")
            for item in itens_escolhidos:
                qtd_comprada = Decimal(str(random.randint(10, 100)))
                valor_un = item.preco_venda
                
                valor_total += qtd_comprada * valor_un
                
                iv = ItemVenda(
                    id_pedido_venda=pedido.id_pedido_venda,
                    id_item=item.id_item,
                    quantidade_vendida=qtd_comprada,
                    valor_unitario=valor_un
                )
                db.add(iv)
            
            pedido.valor_total_pedido = valor_total

            # Histórico do pedido
            db.add(PedidoVendaHistorico(
                id_pedido_venda=pedido.id_pedido_venda,
                id_usuario=usuario.id_usuario,
                nome_usuario=usuario.nome,
                status_novo=status,
                justificativa="Gerado via Seeder",
                data_hora=data_pedido
            ))

            if status in ["Confirmado", "Concluído"]:
                eh_a_vista = random.random() < 0.3
                
                if eh_a_vista:
                    vencimento = data_pedido.date()
                    status_pag = "Pago"
                else:
                    # Vencimento 30, 60 ou 90 dias depois da venda
                    prazo = random.choice([30, 60, 90])
                    vencimento = (data_pedido + timedelta(days=prazo)).date()
                    
                    if vencimento < hoje.date():
                        # Se já passou, tem chance de estar pago ou em atraso (Pendente)
                        status_pag = random.choice(["Pago", "Pendente"]) 
                    else:
                        # Vencimento no futuro
                        status_pag = "Pendente"

                lancamento = LancamentoFinanceiro(
                    id_pedido_venda=pedido.id_pedido_venda,
                    valor=valor_total,
                    data_vencimento=vencimento,
                    tipo_lancamento="CONTA_A_RECEBER",
                    origem_lancamento="VENDA",
                    status_pagamento=status_pag,
                )
                db.add(lancamento)

        db.commit()
        print("✅ Banco de dados populado com sucesso! Acesse o Dashboard para ver os gráficos.")

    except Exception as e:
        db.rollback()
        print(f"❌ Erro ao popular banco: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    gerar_dados_teste()