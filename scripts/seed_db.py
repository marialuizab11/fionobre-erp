import os
import random
from datetime import datetime, timedelta
import sqlalchemy
from faker import Faker
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base

import src.database.models.estoque

from src.database.models import (
    Cliente, Item, Fornecedor, PedidoCompra, ItemCompra, NecessidadeCompra,
    MovimentacaoEstoque, LancamentoFinanceiro, Entrega, EntregaStatusHistorico,
    CentroProducao, FichaTecnica, ItemFichaTecnica, OrdemProducao, ReservaMaterial,
    ConsumoProducao, Perfil, Permissao, Usuario, LogOperacao, PedidoVenda,
    ItemVenda, PedidoVendaHistorico,
)

# Força a leitura do .env em UTF-8
load_dotenv(encoding='utf-8')
fake = Faker('pt_BR')

def seed_database(database_url):
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("Limpando banco de dados existente (CASCADE)...")
        with engine.connect() as connection:
            connection.execute(sqlalchemy.text("DROP SCHEMA public CASCADE;"))
            connection.execute(sqlalchemy.text("CREATE SCHEMA public;"))
            connection.commit()
        
        print("Criando estrutura das tabelas oficiais...")
        Base.metadata.create_all(bind=engine)

        # ---------------------------------------------------------
        # PERMISSÕES, PERFIS E USUÁRIOS
        # ---------------------------------------------------------
        print("Populando permissoes e perfis...")
        perm_vendas = Permissao(codigo='vendas.gerenciar', descricao='Criar e alterar pedidos de venda')
        perm_usuarios = Permissao(codigo='usuarios.gerenciar', descricao='Gerenciar usuarios do sistema')
        perm_producao = Permissao(codigo='producao.gerenciar', descricao='Gerenciar ordens de producao')
        session.add_all([perm_vendas, perm_usuarios, perm_producao])
        session.flush()

        perfil_admin = Perfil(nome='Administrador', descricao='Acesso total ao sistema')
        perfil_operacional = Perfil(nome='Operacional', descricao='Acesso as operacoes diarias')
        perfil_visualizador = Perfil(nome='Visualizador', descricao='Apenas leitura')
        
        perfil_admin.permissoes = [perm_vendas, perm_usuarios, perm_producao]
        perfil_operacional.permissoes = [perm_vendas, perm_producao]
        perfil_visualizador.permissoes = []

        session.add_all([perfil_admin, perfil_operacional, perfil_visualizador])
        session.flush()

        print("Populando usuarios...")
        admin_user = Usuario(
            google_sub='10982374918237',
            email='admin@fionobre.com',
            nome='Carlos Administrador',
            ativo=True,
            id_perfil=perfil_admin.id_perfil,
            ultimo_login_em=datetime.utcnow() - timedelta(days=1)
        )
        session.add(admin_user)
        
        usuarios_op = []
        for i in range(4):
            u = Usuario(
                google_sub=f'PENDENTE_{fake.uuid4()}',
                email=fake.email(),
                nome=fake.name(),
                ativo=True,
                id_perfil=perfil_operacional.id_perfil,
                ultimo_login_em=datetime.utcnow() - timedelta(days=random.randint(1, 30))
            )
            usuarios_op.append(u)
        session.add_all(usuarios_op)
        session.flush()
        todos_usuarios = [admin_user] + usuarios_op
        
        # ---------------------------------------------------------
        # LOCALIZAÇÕES DE ESTOQUE
        # ---------------------------------------------------------
        print("Populando localizacoes de estoque...")
        from src.database.models.estoque import LocalizacaoEstoque, EstoqueLocalizacao
        loc_principal = LocalizacaoEstoque(nome="Armazém Principal", descricao="Galpão central", ativo='S')
        loc_secundaria = LocalizacaoEstoque(nome="Prateleira de Avarias", descricao="Itens com defeito", ativo='S')
        session.add_all([loc_principal, loc_secundaria])
        session.flush()

        # ---------------------------------------------------------
        # ITENS E ESTOQUE
        # ---------------------------------------------------------
        print("Populando itens de estoque...")
        materias_primas = [
            Item(descricao='Tecido de Algodao Cru', tipo_item='MATERIA_PRIMA', unidade_medida='M', saldo_estoque=1500, estoque_minimo=300, custo_medio=12.50),
            Item(descricao='Tecido Poliester Estampado', tipo_item='MATERIA_PRIMA', unidade_medida='M', saldo_estoque=800, estoque_minimo=200, custo_medio=15.00),
            Item(descricao='Linha de Costura Branca', tipo_item='INSUMO', unidade_medida='UN', saldo_estoque=200, estoque_minimo=50, custo_medio=4.00),
            Item(descricao='Botao de Plastico 15mm', tipo_item='INSUMO', unidade_medida='UN', saldo_estoque=5000, estoque_minimo=1000, custo_medio=0.20),
            Item(descricao='Ziper 20cm', tipo_item='INSUMO', unidade_medida='UN', saldo_estoque=600, estoque_minimo=150, custo_medio=1.50)
        ]
        
        produtos_acabados = [
            Item(descricao='Camiseta Basica Branca P', tipo_item='PRODUTO_ACABADO', unidade_medida='UN', saldo_estoque=150, estoque_minimo=30, preco_venda=45.00, custo_medio=18.00),
            Item(descricao='Camiseta Basica M', tipo_item='PRODUTO_ACABADO', unidade_medida='UN', saldo_estoque=200, estoque_minimo=30, preco_venda=45.00, custo_medio=18.00),
            Item(descricao='Calca Sarja 40', tipo_item='PRODUTO_ACABADO', unidade_medida='UN', saldo_estoque=80, estoque_minimo=20, preco_venda=120.00, custo_medio=50.00)
        ]
        
        todos_itens = materias_primas + produtos_acabados
        session.add_all(todos_itens)
        session.flush()
        
        # Sincroniza o saldo_estoque com a nova tabela de EstoqueLocalizacao
        for item in todos_itens:
            el = EstoqueLocalizacao(
                id_item=item.id_item,
                id_localizacao=loc_principal.id_localizacao,
                quantidade=item.saldo_estoque
            )
            session.add(el)
        session.flush()

        # ---------------------------------------------------------
        # CLIENTES E FORNECEDORES
        # ---------------------------------------------------------
        print("Populando clientes e fornecedores...")
        clientes = []
        for _ in range(10):
            clientes.append(Cliente(
                razao_social=fake.company(),
                cnpj_cpf=fake.cnpj() if random.choice([True, False]) else fake.cpf(),
                email=fake.email(),
                telefone=fake.phone_number()[:20],
                cep=fake.postcode(),
                rua=fake.street_name(),
                numero=str(random.randint(1, 2000)),
                bairro=fake.bairro(),
                cidade=fake.city(),
                uf=fake.estado_sigla()
            ))
        session.add_all(clientes)

        fornecedores = []
        for _ in range(5):
            fornecedores.append(Fornecedor(
                razao_social=fake.company(),
                cnpj_cpf=fake.cnpj(),
                email=fake.email(),
                telefone=fake.phone_number()[:20],
                cep=fake.postcode(),
                rua=fake.street_name(),
                numero=str(random.randint(1, 2000)),
                bairro=fake.bairro(),
                cidade=fake.city(),
                uf=fake.estado_sigla()
            ))
        session.add_all(fornecedores)
        session.flush()

        # ---------------------------------------------------------
        # PRODUÇÃO (CENTROS, FICHAS, ORDENS, RESERVAS)
        # ---------------------------------------------------------
        print("Populando centros e fichas tecnicas...")
        centros = [
            CentroProducao(nome='Corte', descricao='Setor de corte', ativo='S'),
            CentroProducao(nome='Costura', descricao='Setor de montagem', ativo='S')
        ]
        session.add_all(centros)
        session.flush()

        for prod in produtos_acabados:
            ft = FichaTecnica(
                id_item_produto=prod.id_item, 
                descricao=f'Ficha de {prod.descricao}',
                ativo='S'
            )
            session.add(ft)
            session.flush()
            
            insumos_escolhidos = random.sample(materias_primas, k=random.randint(2, 3))
            for ins in insumos_escolhidos:
                comp = ItemFichaTecnica(
                    id_ficha_tecnica=ft.id_ficha_tecnica,
                    id_item_insumo=ins.id_item,
                    quantidade_por_unidade=round(random.uniform(0.5, 3.0), 2)
                )
                session.add(comp)
        session.flush()

        print("Populando ordens de producao...")
        status_ops = ['Criado', 'Em Producao', 'Finalizado', 'Cancelado']
        ordens = []
        for _ in range(20):
            status = random.choice(status_ops)
            dt_criacao = fake.date_time_between(start_date=datetime.utcnow() - timedelta(days=60), end_date=datetime.utcnow() - timedelta(days=10))
            dt_inicio = dt_criacao + timedelta(days=1) if status != 'Criado' else None
            dt_fim = dt_inicio + timedelta(days=2) if status == 'Finalizado' else None
            
            op = OrdemProducao(
                id_centro_producao=random.choice(centros).id_centro_producao,
                id_item_produto=random.choice(produtos_acabados).id_item,
                id_usuario=random.choice(todos_usuarios).id_usuario,
                quantidade_planejada=random.choice([50, 100, 200]),
                quantidade_produzida=random.choice([50, 100, 200]) if status == 'Finalizado' else 0,
                status_ordem=status,
                data_criacao=dt_criacao,
                data_inicio=dt_inicio,
                data_finalizacao=dt_fim
            )
            ordens.append(op)
        session.add_all(ordens)
        session.flush()

        for op in ordens:
            if op.status_ordem in ['Criado', 'Em Producao']:
                res = ReservaMaterial(
                    id_ordem_producao=op.id_ordem_producao,
                    id_item_insumo=random.choice(materias_primas).id_item,
                    quantidade_reservada=op.quantidade_planejada * 1.1,
                    quantidade_consumida=op.quantidade_planejada * 1.05 if op.status_ordem == 'Em Producao' else 0,
                    status_reserva='RESERVADA'
                )
                session.add(res)
            if op.status_ordem in ['Em Producao', 'Finalizado']:
                cons = ConsumoProducao(
                    id_ordem_producao=op.id_ordem_producao,
                    id_item_insumo=random.choice(materias_primas).id_item,
                    quantidade=op.quantidade_planejada * 1.05,
                    tipo_registro='CONSUMO',
                    data_registro=op.data_inicio or datetime.utcnow()
                )
                session.add(cons)
        session.flush()

        # ---------------------------------------------------------
        # COMPRAS E VENDAS
        # ---------------------------------------------------------
        print("Populando pedidos de compra e venda...")
        status_compras = ['Criado', 'Confirmado', 'Recebido', 'Cancelado']
        pedidos_compra = []
        for _ in range(15):
            status_c = random.choice(status_compras)
            pc = PedidoCompra(
                id_fornecedor=random.choice(fornecedores).id_fornecedor,
                id_usuario=random.choice(todos_usuarios).id_usuario,
                status_compra=status_c,
                valor_total_pedido=0,
                data_pedido=fake.date_time_between(start_date=datetime.utcnow() - timedelta(days=90), end_date=datetime.utcnow()),
                justificativa_cancelamento='Erro no lote' if status_c == 'Cancelado' else None
            )
            pedidos_compra.append(pc)
        session.add_all(pedidos_compra)
        session.flush()

        for pc in pedidos_compra:
            total = 0
            qtd_itens = random.randint(1, min(4, len(materias_primas)))
            itens_escolhidos = random.sample(materias_primas, k=qtd_itens)
            
            for item_m in itens_escolhidos:
                qtd = random.randint(50, 500)
                custo = item_m.custo_medio or 10.00
                ic = ItemCompra(
                    id_pedido_compra=pc.id_pedido_compra,
                    id_item=item_m.id_item,
                    quantidade_comprada=qtd,
                    custo_unitario=custo
                )
                session.add(ic)
                total += qtd * custo
            pc.valor_total_pedido = total
        session.flush()

        status_vendas = ['Orcamento', 'Criado', 'Confirmado', 'Concluido', 'Cancelado']
        status_entregas = ['Pendente', 'Em separação', 'Enviado', 'Entregue']

        for _ in range(120):
            status_v = random.choice(status_vendas)
            dt_venda = fake.date_time_between(
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2026, 8, 1),
            )

            id_entrega = None
            if status_v != 'Orcamento':
                entrega = Entrega(
                    data_previsao=dt_venda + timedelta(days=5),
                    status_logistica=random.choice(status_entregas),
                    valor_frete=round(random.uniform(15.00, 100.00), 2),
                    data_expedicao=dt_venda + timedelta(days=1),
                    data_entrega_realizada=dt_venda + timedelta(days=4) if status_v == 'Concluido' else None
                )
                session.add(entrega)
                session.flush()
                id_entrega = entrega.id_entrega

                session.add(EntregaStatusHistorico(
                    id_entrega=entrega.id_entrega,
                    id_usuario=admin_user.id_usuario,
                    nome_usuario=admin_user.nome,
                    status_anterior='Pendente',
                    status_novo=entrega.status_logistica,
                    data_hora=dt_venda
                ))

            pv = PedidoVenda(
                id_cliente=random.choice(clientes).id_cliente,
                id_usuario=random.choice(todos_usuarios).id_usuario,
                id_entrega=id_entrega,
                status_venda=status_v,
                valor_total_pedido=0,
                data_venda=dt_venda
            )
            session.add(pv)
            session.flush()

            session.add(PedidoVendaHistorico(
                id_pedido_venda=pv.id_pedido_venda,
                id_usuario=admin_user.id_usuario,
                nome_usuario=admin_user.nome,
                status_novo=pv.status_venda,
                data_hora=dt_venda
            ))

            total_venda = 0
            qtd_produtos = random.randint(1, min(3, len(produtos_acabados)))
            produtos_escolhidos = random.sample(produtos_acabados, k=qtd_produtos)

            for prod in produtos_escolhidos:
                qtd = random.randint(2, 20)
                v_unit = prod.preco_venda or 50.00
                iv = ItemVenda(
                    id_pedido_venda=pv.id_pedido_venda,
                    id_item=prod.id_item,
                    quantidade_vendida=qtd,
                    valor_unitario=v_unit
                )
                session.add(iv)
                total_venda += qtd * v_unit
            pv.valor_total_pedido = total_venda
            session.flush()

            if status_v != 'Orcamento':
                lf_receber = LancamentoFinanceiro(
                    id_pedido_venda=pv.id_pedido_venda,
                    valor=total_venda,
                    data_vencimento=dt_venda + timedelta(days=30),
                    tipo_lancamento='CONTA_A_RECEBER',
                    origem_lancamento='VENDA',
                    status_pagamento='Pago' if status_v == 'Concluido' else 'Pendente',
                    data_pagamento=dt_venda + timedelta(days=10) if status_v == 'Concluido' else None
                )
                session.add(lf_receber)

        for pc in pedidos_compra:
            if pc.status_compra == 'Recebido':
                lf_pagar = LancamentoFinanceiro(
                    id_pedido_compra=pc.id_pedido_compra,
                    valor=pc.valor_total_pedido,
                    data_vencimento=pc.data_pedido + timedelta(days=30),
                    tipo_lancamento='CONTA_A_PAGAR',
                    origem_lancamento='COMPRA',
                    status_pagamento='Pago',
                    data_pagamento=pc.data_pedido + timedelta(days=15)
                )
                session.add(lf_pagar)

        # ---------------------------------------------------------
        # MOVIMENTAÇÃO DE ESTOQUE E LOGS
        # ---------------------------------------------------------
        print("Populando logs e movimentacoes de estoque...")
        for item in todos_itens:
            mov = MovimentacaoEstoque(
                id_item=item.id_item,
                id_usuario=admin_user.id_usuario,
                quantidade=item.saldo_estoque,
                tipo_movimento='SALDO_INICIAL',
                data_movimento=datetime.utcnow() - timedelta(days=100),
                id_local_destino=loc_principal.id_localizacao
            )
            session.add(mov)

        for _ in range(30):
            log = LogOperacao(
                id_usuario=random.choice(todos_usuarios).id_usuario,
                modulo=random.choice(['VENDAS', 'COMPRAS', 'PRODUCAO']),
                acao=random.choice(['CRIAR', 'ATUALIZAR', 'CANCELAR']),
                entidade='Sistema',
                id_registro=str(random.randint(1, 100)),
                detalhes='{"status": "sucesso"}',
                data_hora=fake.date_time_between(start_date=datetime.utcnow() - timedelta(days=30), end_date=datetime.utcnow())
            )
            session.add(log)

        session.commit()
        print("\n--- SEED REALIZADO COM SUCESSO ---")

    except Exception as e:
        session.rollback()
        print(f"Erro durante o processo de seed: {e}")
        raise
    finally:
        session.close()

if __name__ == '__main__':
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME")
    
    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    seed_database(database_url=db_url)