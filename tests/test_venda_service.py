import unittest
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base
from src.database.models.cadastros import Item
from src.database.models.core import MovimentacaoEstoque
from src.database.models.usuarios import LogOperacao
from src.database.models.vendas import PedidoVenda
from src.services.auth_service import criar_contexto_usuario, sincronizar_usuario_google
from src.services.cadastro_service import criar_cliente, criar_item
from src.services.venda_service import criar_pedido_venda


def claims_google(sub: str, email: str) -> dict:
    return {
        "sub": sub,
        "email": email,
        "email_verified": True,
        "name": "Usuário Teste",
    }


class VendaServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        admin = sincronizar_usuario_google(
            self.db,
            claims_google("admin-google", "admin@example.com"),
            admin_emails={"admin@example.com"},
        )
        self.admin = criar_contexto_usuario(admin)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _criar_cadastros(self):
        cliente = criar_cliente(
            self.db,
            self.admin,
            "Cliente Teste",
            "12345678900",
        )
        item = criar_item(
            self.db,
            self.admin,
            "Tecido Premium",
            "M",
            "PRODUTO_ACABADO",
            saldo_inicial=10,
            estoque_minimo=2,
            preco_venda="12.50",
            custo_medio="7.00",
        )
        return cliente, item

    def test_venda_baixa_estoque_e_registra_auditoria(self):
        cliente, item = self._criar_cadastros()

        pedido = criar_pedido_venda(
            self.db,
            cliente.id_cliente,
            [{"id_item": item.id_item, "quantidade": 2, "valor_unitario": "12.50"}],
            self.admin,
        )

        item_atualizado = self.db.get(Item, item.id_item)
        self.assertEqual(Decimal("25.00"), pedido.valor_total_pedido)
        self.assertEqual(Decimal("8.00"), item_atualizado.saldo_estoque)
        self.assertEqual(2, self.db.query(MovimentacaoEstoque).count())
        self.assertEqual(
            1,
            self.db.query(LogOperacao)
            .filter(LogOperacao.acao == "CONFIRMAR_PEDIDO")
            .count(),
        )

    def test_venda_sem_saldo_desfaz_toda_transacao(self):
        cliente, item = self._criar_cadastros()

        with self.assertRaises(ValueError):
            criar_pedido_venda(
                self.db,
                cliente.id_cliente,
                [{"id_item": item.id_item, "quantidade": 20, "valor_unitario": 10}],
                self.admin,
            )

        self.assertEqual(0, self.db.query(PedidoVenda).count())
        self.assertEqual(Decimal("10.00"), self.db.get(Item, item.id_item).saldo_estoque)
        self.assertEqual(1, self.db.query(MovimentacaoEstoque).count())

    def test_visualizador_nao_pode_cadastrar_cliente(self):
        usuario = sincronizar_usuario_google(
            self.db,
            claims_google("viewer-google", "viewer@example.com"),
        )
        viewer = criar_contexto_usuario(usuario)

        with self.assertRaises(PermissionError):
            criar_cliente(self.db, viewer, "Sem permissão", "99999999999")


if __name__ == "__main__":
    unittest.main()
