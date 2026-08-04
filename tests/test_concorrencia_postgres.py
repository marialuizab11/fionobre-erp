import os
import threading
import unittest
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base
from src.database.models.cadastros import Item
from src.database.models.producao import OrdemProducao, ReservaMaterial
from src.database.models.vendas import PedidoVenda
from src.services.auth_service import criar_contexto_usuario, sincronizar_usuario_google
from src.services.cadastro_service import criar_cliente, criar_item
from src.services.producao_service import (
    criar_centro_producao,
    criar_ordem_producao,
    salvar_ficha_tecnica,
)
from src.services.venda_service import criar_pedido_venda


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@unittest.skipUnless(TEST_DATABASE_URL, "Requer TEST_DATABASE_URL com PostgreSQL isolado")
class ConcorrenciaPostgresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        cls.Session = sessionmaker(bind=cls.engine, expire_on_commit=False)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        db = self.Session()
        try:
            usuario = sincronizar_usuario_google(
                db,
                {
                    "sub": "concorrencia-google",
                    "email": "concorrencia@example.com",
                    "email_verified": True,
                    "name": "Teste Concorrência",
                },
                admin_emails={"concorrencia@example.com"},
            )
            self.usuario = criar_contexto_usuario(usuario)
        finally:
            db.close()

    def _executar_simultaneamente(self, operacao):
        barreira = threading.Barrier(2)
        resultados = []
        trava = threading.Lock()

        def executar():
            db = self.Session()
            try:
                barreira.wait(timeout=10)
                operacao(db)
                resultado = "sucesso"
            except Exception as erro:
                resultado = f"erro:{type(erro).__name__}:{erro}"
            finally:
                db.close()
            with trava:
                resultados.append(resultado)

        threads = [threading.Thread(target=executar) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        return resultados

    def test_duas_ordens_nao_reservam_o_mesmo_saldo(self):
        db = self.Session()
        try:
            insumo = criar_item(
                db, self.usuario, "Insumo concorrente", "KG", "MATERIA_PRIMA",
                saldo_inicial=10,
            )
            produto = criar_item(
                db, self.usuario, "Produto concorrente", "UN", "PRODUTO_ACABADO"
            )
            centro = criar_centro_producao(
                db, "Centro concorrente", "Teste", self.usuario.id_usuario
            )
            salvar_ficha_tecnica(
                db,
                produto.id_item,
                [{"id_item_insumo": insumo.id_item, "quantidade_por_unidade": 2}],
                self.usuario.id_usuario,
            )
            ids = (centro.id_centro_producao, produto.id_item)
        finally:
            db.close()

        resultados = self._executar_simultaneamente(
            lambda sessao: criar_ordem_producao(
                sessao, ids[0], ids[1], 3, self.usuario.id_usuario
            )
        )
        self.assertEqual(1, resultados.count("sucesso"), resultados)
        self.assertEqual(1, sum(item.startswith("erro:ValueError") for item in resultados), resultados)

        db = self.Session()
        try:
            self.assertEqual(1, db.query(OrdemProducao).count())
            reservado = sum(
                Decimal(str(item.quantidade_reservada))
                for item in db.query(ReservaMaterial).filter_by(status_reserva="RESERVADA")
            )
            self.assertEqual(Decimal("6.0000"), reservado)
        finally:
            db.close()

    def test_duas_vendas_nao_baixam_estoque_abaixo_de_zero(self):
        db = self.Session()
        try:
            produto = criar_item(
                db, self.usuario, "Produto para venda", "UN", "PRODUTO_ACABADO",
                saldo_inicial=5, preco_venda=20,
            )
            cliente = criar_cliente(
                db, self.usuario, "Cliente concorrente", "44455566677"
            )
            ids = (cliente.id_cliente, produto.id_item)
        finally:
            db.close()

        resultados = self._executar_simultaneamente(
            lambda sessao: criar_pedido_venda(
                sessao,
                ids[0],
                [{"id_item": ids[1], "quantidade": 4, "valor_unitario": 20}],
                self.usuario,
            )
        )
        self.assertEqual(1, resultados.count("sucesso"), resultados)
        self.assertEqual(1, sum(item.startswith("erro:ValueError") for item in resultados), resultados)

        db = self.Session()
        try:
            self.assertEqual(Decimal("1.00"), db.get(Item, ids[1]).saldo_estoque)
            self.assertEqual(1, db.query(PedidoVenda).count())
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
