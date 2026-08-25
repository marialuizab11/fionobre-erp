import unittest
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base
from src.database.models.cadastros import Item
from src.database.models.compras import Fornecedor, ItemCompra, PedidoCompra
import src.database.models.estoque  # noqa: F401 - registra tabelas relacionadas no metadata
from src.services.bi_suprimentos_service import (
    calcular_indicadores_suprimentos,
    calcular_necessidades_reposicao,
)


class IndicadoresSuprimentosTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

        self.db.add_all(
            [
                Item(descricao="Camiseta", tipo_item="PRODUTO_ACABADO", unidade_medida="UN", saldo_estoque=10, estoque_minimo=5, custo_medio=20),
                Item(descricao="Tecido", tipo_item="MATERIA_PRIMA", unidade_medida="M", saldo_estoque=2, estoque_minimo=10, custo_medio=15),
                Item(descricao="Linha", tipo_item="INSUMO", unidade_medida="UN", saldo_estoque=5, estoque_minimo=5, custo_medio=2),
            ]
        )
        fornecedor = Fornecedor(razao_social="Fornecedor", cnpj_cpf="123")
        self.db.add(fornecedor)
        self.db.flush()
        self.db.add_all(
            [
                PedidoCompra(id_fornecedor=fornecedor.id_fornecedor, id_usuario=1, data_pedido=datetime(2026, 8, 10, 12), status_compra="Confirmado", valor_total_pedido=100),
                PedidoCompra(id_fornecedor=fornecedor.id_fornecedor, id_usuario=1, data_pedido=datetime(2026, 8, 20, 23, 59), status_compra="Recebido", valor_total_pedido=250),
                PedidoCompra(id_fornecedor=fornecedor.id_fornecedor, id_usuario=1, data_pedido=datetime(2026, 8, 15), status_compra="Criado", valor_total_pedido=999),
                PedidoCompra(id_fornecedor=fornecedor.id_fornecedor, id_usuario=1, data_pedido=datetime(2026, 7, 31), status_compra="Recebido", valor_total_pedido=500),
            ]
        )
        self.db.flush()
        tecido = self.db.query(Item).filter(Item.descricao == "Tecido").one()
        pedido_confirmado = self.db.query(PedidoCompra).filter(
            PedidoCompra.valor_total_pedido == 100
        ).one()
        pedido_criado = self.db.query(PedidoCompra).filter(
            PedidoCompra.status_compra == "Criado"
        ).one()
        pedido_recebido = self.db.query(PedidoCompra).filter(
            PedidoCompra.valor_total_pedido == 250
        ).one()
        self.db.add_all(
            [
                ItemCompra(id_pedido_compra=pedido_confirmado.id_pedido_compra, id_item=tecido.id_item, quantidade_comprada=3, custo_unitario=10),
                ItemCompra(id_pedido_compra=pedido_criado.id_pedido_compra, id_item=tecido.id_item, quantidade_comprada=2, custo_unitario=10),
                ItemCompra(id_pedido_compra=pedido_recebido.id_pedido_compra, id_item=tecido.id_item, quantidade_comprada=50, custo_unitario=10),
            ]
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_calcula_kpis_e_distribuicao_por_tipo(self):
        indicadores = calcular_indicadores_suprimentos(
            self.db, date(2026, 8, 1), date(2026, 8, 20)
        )

        self.assertEqual(Decimal("240.00"), indicadores.valor_imobilizado)
        self.assertEqual(1, indicadores.itens_em_ruptura)
        self.assertEqual(Decimal("350.00"), indicadores.custo_total_aquisicao)
        self.assertEqual(
            {"Produto Acabado": 200.0, "Matéria-Prima": 30.0, "Insumo": 10.0},
            {linha["Tipo de item"]: linha["Valor em estoque"] for linha in indicadores.valor_por_tipo},
        )

    def test_rejeita_periodo_invertido(self):
        with self.assertRaisesRegex(ValueError, "data inicial"):
            calcular_indicadores_suprimentos(
                self.db, date(2026, 8, 20), date(2026, 8, 1)
            )

    def test_sugere_reposicao_descontando_apenas_compras_abertas(self):
        necessidades = calcular_necessidades_reposicao(self.db)
        por_item = {registro["Item"]: registro for registro in necessidades}

        self.assertEqual(5.0, por_item["Tecido"]["Em compra"])
        self.assertEqual(3.0, por_item["Tecido"]["Sugestão de compra"])
        self.assertEqual("Urgente", por_item["Tecido"]["Situação"])
        self.assertEqual(0.0, por_item["Linha"]["Sugestão de compra"])
        self.assertEqual("Normal", por_item["Linha"]["Situação"])

    def test_classifica_estoque_zerado_e_compra_que_cobre_deficit(self):
        item_zerado = Item(
            descricao="Zíper",
            tipo_item="INSUMO",
            unidade_medida="UN",
            saldo_estoque=0,
            estoque_minimo=10,
            custo_medio=1,
        )
        item_critico = Item(
            descricao="Botão",
            tipo_item="INSUMO",
            unidade_medida="UN",
            saldo_estoque=0,
            estoque_minimo=20,
            custo_medio=1,
        )
        self.db.add_all([item_zerado, item_critico])
        self.db.flush()
        pedido_confirmado = self.db.query(PedidoCompra).filter(
            PedidoCompra.valor_total_pedido == 100
        ).one()
        self.db.add(
            ItemCompra(
                id_pedido_compra=pedido_confirmado.id_pedido_compra,
                id_item=item_zerado.id_item,
                quantidade_comprada=10,
                custo_unitario=1,
            )
        )
        self.db.commit()

        por_item = {
            registro["Item"]: registro
            for registro in calcular_necessidades_reposicao(self.db)
        }
        self.assertEqual(0.0, por_item["Zíper"]["Sugestão de compra"])
        self.assertEqual("Compra em andamento", por_item["Zíper"]["Situação"])
        self.assertEqual(20.0, por_item["Botão"]["Sugestão de compra"])
        self.assertEqual("Crítico", por_item["Botão"]["Situação"])


if __name__ == "__main__":
    unittest.main()
