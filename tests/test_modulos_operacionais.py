import unittest
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base
from src.database.models.cadastros import Item
from src.database.models.compras import NecessidadeCompra
from src.database.models.core import MovimentacaoEstoque
from src.database.models.financeiro import LancamentoFinanceiro
from src.database.models.logistica import Entrega
from src.database.models.usuarios import LogOperacao
from src.database.models.vendas import PedidoVenda
from src.services import compra_service, producao_service
from src.services.auth_service import criar_contexto_usuario, sincronizar_usuario_google
from src.services.cadastro_service import criar_cliente, criar_item
from src.services.financeiro_service import criar_conta_a_receber
from src.services.logistica_service import criar_entrega_para_pedido
from src.services.venda_service import criar_pedido_venda


def _claims_google():
    return {
        "sub": "operacional-google",
        "email": "operacional@example.com",
        "email_verified": True,
        "name": "Usuário Operacional",
    }


class ModulosOperacionaisTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        usuario = sincronizar_usuario_google(
            self.db,
            _claims_google(),
            admin_emails={"operacional@example.com"},
        )
        self.usuario = criar_contexto_usuario(usuario)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_compras_e_producao_usam_o_log_centralizado(self):
        self.assertIsNotNone(compra_service)
        self.assertIsNotNone(producao_service)
        self.assertIs(Base.metadata.tables["log_operacao"], LogOperacao.__table__)

    def test_compra_recebida_aumenta_estoque_e_gera_conta_pagar(self):
        materia_prima = criar_item(
            self.db, self.usuario, "Tecido cru", "M", "MATERIA_PRIMA",
            saldo_inicial=2, custo_medio=5,
        )
        fornecedor = compra_service.criar_fornecedor(
            self.db, "Fornecedor Teste", "12345678000100", self.usuario.id_usuario
        )
        pedido = compra_service.criar_pedido_compra(
            self.db,
            fornecedor.id_fornecedor,
            [{"id_item": materia_prima.id_item, "quantidade": 8, "custo_unitario": 10}],
            self.usuario.id_usuario,
        )
        compra_service.confirmar_compra(self.db, pedido.id_pedido_compra, self.usuario.id_usuario)
        compra_service.receber_compra(
            self.db,
            pedido.id_pedido_compra,
            date.today() + timedelta(days=30),
            self.usuario.id_usuario,
        )

        self.assertEqual(Decimal("10.00"), self.db.get(Item, materia_prima.id_item).saldo_estoque)
        lancamento = self.db.query(LancamentoFinanceiro).one()
        self.assertEqual("CONTA_A_PAGAR", lancamento.tipo_lancamento)
        self.assertEqual(Decimal("80.00"), lancamento.valor)

    def test_producao_finalizada_consume_insumo_e_adiciona_produto(self):
        insumo = criar_item(
            self.db, self.usuario, "Linha", "UN", "INSUMO", saldo_inicial=10,
        )
        produto = criar_item(
            self.db, self.usuario, "Camiseta", "UN", "PRODUTO_ACABADO",
        )
        centro = producao_service.criar_centro_producao(
            self.db, "Confecção", "Linha principal", self.usuario.id_usuario
        )
        producao_service.salvar_ficha_tecnica(
            self.db,
            produto.id_item,
            [{"id_item_insumo": insumo.id_item, "quantidade_por_unidade": 2}],
            self.usuario.id_usuario,
        )
        ordem = producao_service.criar_ordem_producao(
            self.db, centro.id_centro_producao, produto.id_item, 3, self.usuario.id_usuario
        )
        producao_service.iniciar_producao(self.db, ordem.id_ordem_producao, self.usuario.id_usuario)
        producao_service.registrar_consumo(
            self.db, ordem.id_ordem_producao, insumo.id_item, 4, self.usuario.id_usuario
        )
        producao_service.finalizar_producao(
            self.db, ordem.id_ordem_producao, 3, self.usuario.id_usuario
        )

        self.assertEqual(Decimal("6.00"), self.db.get(Item, insumo.id_item).saldo_estoque)
        self.assertEqual(Decimal("3.00"), self.db.get(Item, produto.id_item).saldo_estoque)
        self.assertEqual("CONSUMIDA", ordem.reservas[0].status_reserva)
        self.assertEqual(Decimal("4"), ordem.reservas[0].quantidade_consumida)

    def test_ficha_calcula_necessidade_e_bloqueia_ordem_sem_material(self):
        insumo = criar_item(
            self.db, self.usuario, "Tecido", "M", "MATERIA_PRIMA", saldo_inicial=5,
        )
        produto = criar_item(
            self.db, self.usuario, "Calça", "UN", "PRODUTO_ACABADO",
        )
        centro = producao_service.criar_centro_producao(
            self.db, "Corte", "Setor de corte", self.usuario.id_usuario
        )
        producao_service.salvar_ficha_tecnica(
            self.db,
            produto.id_item,
            [{"id_item_insumo": insumo.id_item, "quantidade_por_unidade": "1.5"}],
            self.usuario.id_usuario,
        )

        necessidade = producao_service.calcular_necessidade_materiais(
            self.db, produto.id_item, 4
        )[0]
        self.assertEqual(Decimal("6.0000"), necessidade["quantidade_necessaria"])
        self.assertEqual(Decimal("1.0000"), necessidade["quantidade_faltante"])

        with self.assertRaisesRegex(ValueError, "Estoque insuficiente"):
            producao_service.criar_ordem_producao(
                self.db,
                centro.id_centro_producao,
                produto.id_item,
                4,
                self.usuario.id_usuario,
            )

        registros = compra_service.gerar_necessidades_compra(
            self.db, produto.id_item, [necessidade], self.usuario.id_usuario
        )
        compra_service.gerar_necessidades_compra(
            self.db, produto.id_item, [necessidade], self.usuario.id_usuario
        )
        self.assertEqual(1, self.db.query(NecessidadeCompra).count())
        fornecedor = compra_service.criar_fornecedor(
            self.db, "Tecidos SA", "98765432000100", self.usuario.id_usuario
        )
        pedido = compra_service.criar_pedido_por_necessidades(
            self.db,
            fornecedor.id_fornecedor,
            [registros[0].id_necessidade],
            {insumo.id_item: 10},
            self.usuario.id_usuario,
        )
        self.assertEqual("EM_COMPRA", registros[0].status_necessidade)
        compra_service.confirmar_compra(self.db, pedido.id_pedido_compra, self.usuario.id_usuario)
        compra_service.receber_compra(
            self.db,
            pedido.id_pedido_compra,
            date.today() + timedelta(days=30),
            self.usuario.id_usuario,
        )
        self.assertEqual("ATENDIDA", registros[0].status_necessidade)
        ordem = producao_service.criar_ordem_producao(
            self.db,
            centro.id_centro_producao,
            produto.id_item,
            4,
            self.usuario.id_usuario,
        )
        self.assertEqual("Criado", ordem.status_ordem)

    def test_reserva_impede_duplo_uso_e_cancelamento_libera_material(self):
        insumo = criar_item(
            self.db, self.usuario, "Malha", "M", "MATERIA_PRIMA", saldo_inicial=10,
        )
        produto = criar_item(
            self.db, self.usuario, "Blusa", "UN", "PRODUTO_ACABADO",
        )
        centro = producao_service.criar_centro_producao(
            self.db, "Costura", "Costura geral", self.usuario.id_usuario
        )
        producao_service.salvar_ficha_tecnica(
            self.db,
            produto.id_item,
            [{"id_item_insumo": insumo.id_item, "quantidade_por_unidade": 2}],
            self.usuario.id_usuario,
        )
        primeira = producao_service.criar_ordem_producao(
            self.db, centro.id_centro_producao, produto.id_item, 3, self.usuario.id_usuario
        )

        necessidade = producao_service.calcular_necessidade_materiais(
            self.db, produto.id_item, 3
        )[0]
        self.assertEqual(Decimal("6.0000"), necessidade["quantidade_reservada"])
        self.assertEqual(Decimal("4.0000"), necessidade["saldo_disponivel"])
        with self.assertRaisesRegex(ValueError, "Estoque insuficiente"):
            producao_service.criar_ordem_producao(
                self.db, centro.id_centro_producao, produto.id_item, 3, self.usuario.id_usuario
            )

        producao_service.cancelar_ordem_producao(
            self.db, primeira.id_ordem_producao, "Mudança no planejamento", self.usuario.id_usuario
        )
        segunda = producao_service.criar_ordem_producao(
            self.db, centro.id_centro_producao, produto.id_item, 3, self.usuario.id_usuario
        )
        self.assertEqual("Criado", segunda.status_ordem)
        self.assertEqual("LIBERADA", primeira.reservas[0].status_reserva)

    def test_fluxo_completo_da_compra_ate_a_venda(self):
        materia_prima = criar_item(
            self.db, self.usuario, "Algodão", "KG", "MATERIA_PRIMA"
        )
        produto = criar_item(
            self.db, self.usuario, "Fio Premium", "UN", "PRODUTO_ACABADO",
            preco_venda=50,
        )
        cliente = criar_cliente(
            self.db, self.usuario, "Cliente Final", "11122233344"
        )
        fornecedor = compra_service.criar_fornecedor(
            self.db, "Algodão Brasil", "11222333000144", self.usuario.id_usuario
        )
        centro = producao_service.criar_centro_producao(
            self.db, "Fiação", "Centro principal", self.usuario.id_usuario
        )
        producao_service.salvar_ficha_tecnica(
            self.db,
            produto.id_item,
            [{"id_item_insumo": materia_prima.id_item, "quantidade_por_unidade": 2}],
            self.usuario.id_usuario,
        )

        calculo = producao_service.calcular_necessidade_materiais(
            self.db, produto.id_item, 5
        )
        self.assertEqual(Decimal("10.0000"), calculo[0]["quantidade_faltante"])
        necessidades = compra_service.gerar_necessidades_compra(
            self.db, produto.id_item, calculo, self.usuario.id_usuario
        )
        compra = compra_service.criar_pedido_por_necessidades(
            self.db,
            fornecedor.id_fornecedor,
            [necessidades[0].id_necessidade],
            {materia_prima.id_item: 8},
            self.usuario.id_usuario,
        )
        compra_service.confirmar_compra(
            self.db, compra.id_pedido_compra, self.usuario.id_usuario
        )
        compra_service.receber_compra(
            self.db,
            compra.id_pedido_compra,
            date.today() + timedelta(days=30),
            self.usuario.id_usuario,
        )
        self.assertEqual(Decimal("10.00"), materia_prima.saldo_estoque)
        self.assertEqual("ATENDIDA", necessidades[0].status_necessidade)

        ordem = producao_service.criar_ordem_producao(
            self.db, centro.id_centro_producao, produto.id_item, 5,
            self.usuario.id_usuario,
        )
        self.assertEqual(Decimal("10.0000"), ordem.reservas[0].quantidade_reservada)
        producao_service.iniciar_producao(
            self.db, ordem.id_ordem_producao, self.usuario.id_usuario
        )
        producao_service.registrar_consumo(
            self.db, ordem.id_ordem_producao, materia_prima.id_item, 9,
            self.usuario.id_usuario,
        )
        producao_service.registrar_perda(
            self.db, ordem.id_ordem_producao, materia_prima.id_item, 1,
            self.usuario.id_usuario,
        )
        producao_service.finalizar_producao(
            self.db, ordem.id_ordem_producao, 5, self.usuario.id_usuario
        )
        self.assertEqual(Decimal("0.00"), materia_prima.saldo_estoque)
        self.assertEqual(Decimal("5.00"), produto.saldo_estoque)

        venda = criar_pedido_venda(
            self.db,
            cliente.id_cliente,
            [{"id_item": produto.id_item, "quantidade": 2, "valor_unitario": 50}],
            self.usuario,
        )
        criar_conta_a_receber(
            self.db,
            venda.id_pedido_venda,
            100,
            date.today() + timedelta(days=30),
        )
        entrega = criar_entrega_para_pedido(
            self.db,
            venda.id_pedido_venda,
            date.today() + timedelta(days=7),
            0,
        )

        self.assertEqual(Decimal("3.00"), produto.saldo_estoque)
        self.assertEqual(1, self.db.query(PedidoVenda).count())
        self.assertEqual(1, self.db.query(Entrega).count())
        self.assertEqual(entrega.id_entrega, venda.id_entrega)
        self.assertEqual(2, self.db.query(LancamentoFinanceiro).count())
        self.assertEqual(4, self.db.query(MovimentacaoEstoque).count())
        self.assertGreaterEqual(self.db.query(LogOperacao).count(), 10)

    def test_apontamento_acima_da_reserva_e_bloqueado(self):
        insumo = criar_item(
            self.db, self.usuario, "Elástico", "M", "INSUMO", saldo_inicial=5
        )
        produto = criar_item(
            self.db, self.usuario, "Short", "UN", "PRODUTO_ACABADO"
        )
        centro = producao_service.criar_centro_producao(
            self.db, "Acabamento", "Centro de acabamento", self.usuario.id_usuario
        )
        producao_service.salvar_ficha_tecnica(
            self.db,
            produto.id_item,
            [{"id_item_insumo": insumo.id_item, "quantidade_por_unidade": 1}],
            self.usuario.id_usuario,
        )
        ordem = producao_service.criar_ordem_producao(
            self.db, centro.id_centro_producao, produto.id_item, 2,
            self.usuario.id_usuario,
        )
        producao_service.iniciar_producao(
            self.db, ordem.id_ordem_producao, self.usuario.id_usuario
        )
        with self.assertRaisesRegex(ValueError, "supera a quantidade reservada"):
            producao_service.registrar_consumo(
                self.db, ordem.id_ordem_producao, insumo.id_item, 3,
                self.usuario.id_usuario,
            )
        self.assertEqual(0, len(ordem.consumos))
        self.assertEqual(Decimal("5.00"), insumo.saldo_estoque)

    def test_cancelamento_de_compra_nao_retira_material_reservado(self):
        insumo = criar_item(
            self.db, self.usuario, "Tinta", "L", "MATERIA_PRIMA"
        )
        produto = criar_item(
            self.db, self.usuario, "Tecido tingido", "M", "PRODUTO_ACABADO"
        )
        fornecedor = compra_service.criar_fornecedor(
            self.db, "Tintas Ltda", "55666777000188", self.usuario.id_usuario
        )
        centro = producao_service.criar_centro_producao(
            self.db, "Tinturaria", "Centro de tingimento", self.usuario.id_usuario
        )
        producao_service.salvar_ficha_tecnica(
            self.db,
            produto.id_item,
            [{"id_item_insumo": insumo.id_item, "quantidade_por_unidade": 2}],
            self.usuario.id_usuario,
        )
        compra = compra_service.criar_pedido_compra(
            self.db,
            fornecedor.id_fornecedor,
            [{"id_item": insumo.id_item, "quantidade": 10, "custo_unitario": 4}],
            self.usuario.id_usuario,
        )
        compra_service.confirmar_compra(
            self.db, compra.id_pedido_compra, self.usuario.id_usuario
        )
        compra_service.receber_compra(
            self.db,
            compra.id_pedido_compra,
            date.today() + timedelta(days=30),
            self.usuario.id_usuario,
        )
        producao_service.criar_ordem_producao(
            self.db, centro.id_centro_producao, produto.id_item, 5,
            self.usuario.id_usuario,
        )

        with self.assertRaisesRegex(RuntimeError, "Saldo insuficiente"):
            compra_service.cancelar_compra(
                self.db,
                compra.id_pedido_compra,
                "Compra será substituída",
                self.usuario.id_usuario,
            )
        self.db.refresh(compra)
        self.db.refresh(insumo)
        self.assertEqual("Recebido", compra.status_compra)
        self.assertEqual(Decimal("10.00"), insumo.saldo_estoque)


if __name__ == "__main__":
    unittest.main()
