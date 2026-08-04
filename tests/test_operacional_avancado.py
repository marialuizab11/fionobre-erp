import unittest
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base
from src.database.models.cadastros import Item
from src.database.models.logistica import ComprovanteEntrega, EventoRastreamentoEntrega
from src.database.models.producao import AlocacaoCapacidadeProducao
from src.services import producao_service
from src.services.auth_service import criar_contexto_usuario, sincronizar_usuario_google
from src.services.cadastro_service import criar_cliente, criar_item
from src.services.logistica_service import (
    configurar_rastreamento_externo,
    criar_entrega_para_pedido,
    criar_rota_entrega,
    criar_veiculo,
    finalizar_rota,
    iniciar_rota,
    receber_devolucao,
    registrar_comprovante_entrega,
    registrar_evento_rastreamento,
    solicitar_devolucao,
)
from src.services.venda_service import criar_pedido_venda


def claims_google() -> dict:
    return {
        "sub": "operacional-avancado",
        "email": "operacional-avancado@example.com",
        "email_verified": True,
        "name": "Operador Avançado",
    }


def proximo_dia_util() -> date:
    dia = date.today()
    while dia.weekday() > 4:
        dia += timedelta(days=1)
    return dia


class OperacionalAvancadoTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        usuario = sincronizar_usuario_google(
            self.db,
            claims_google(),
            admin_emails={"operacional-avancado@example.com"},
        )
        self.usuario = criar_contexto_usuario(usuario)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _estrutura_producao(self):
        insumo = criar_item(
            self.db,
            self.usuario,
            "Tecido para roteiro",
            "M",
            "MATERIA_PRIMA",
            saldo_inicial=100,
        )
        produto = criar_item(
            self.db,
            self.usuario,
            "Produto roteirizado",
            "UN",
            "PRODUTO_ACABADO",
        )
        centro = producao_service.criar_centro_producao(
            self.db, "Corte programado", "Centro com agenda", self.usuario.id_usuario
        )
        producao_service.configurar_capacidade_centro(
            self.db, centro.id_centro_producao, 8, self.usuario.id_usuario
        )
        producao_service.salvar_ficha_tecnica(
            self.db,
            produto.id_item,
            [{"id_item_insumo": insumo.id_item, "quantidade_por_unidade": 1}],
            self.usuario.id_usuario,
        )
        roteiro = producao_service.salvar_roteiro_producao(
            self.db,
            produto.id_item,
            [
                {
                    "id_centro_producao": centro.id_centro_producao,
                    "nome_operacao": "Cortar",
                    "recurso": "Mesa 1",
                    "tempo_setup_horas": 1,
                    "tempo_unitario_horas": 1,
                }
            ],
            self.usuario.id_usuario,
        )
        return insumo, produto, centro, roteiro

    def test_planejamento_distribui_ordens_sem_exceder_capacidade_diaria(self):
        _, produto, centro, roteiro = self._estrutura_producao()
        inicio = proximo_dia_util()
        primeira = producao_service.criar_ordem_producao(
            self.db,
            centro.id_centro_producao,
            produto.id_item,
            4,
            self.usuario.id_usuario,
            inicio,
            roteiro.id_roteiro,
        )
        segunda = producao_service.criar_ordem_producao(
            self.db,
            centro.id_centro_producao,
            produto.id_item,
            4,
            self.usuario.id_usuario,
            inicio,
            roteiro.id_roteiro,
        )

        self.assertEqual(Decimal("5.00"), primeira.planejamento.carga_total_horas)
        self.assertEqual(2, len(segunda.operacoes[0].alocacoes))
        cargas = producao_service.consultar_carga_centros(
            self.db, inicio, inicio + timedelta(days=7)
        )
        self.assertTrue(cargas)
        self.assertTrue(all(item["alocado"] <= Decimal("8.00") for item in cargas))
        self.assertEqual(
            Decimal("10.00"),
            sum((item["alocado"] for item in cargas), Decimal("0.00")),
        )

    def test_roteiro_exige_inspecao_final_aprovada(self):
        insumo, produto, centro, roteiro = self._estrutura_producao()
        ordem = producao_service.criar_ordem_producao(
            self.db,
            centro.id_centro_producao,
            produto.id_item,
            2,
            self.usuario.id_usuario,
            proximo_dia_util(),
            roteiro.id_roteiro,
        )
        producao_service.iniciar_producao(
            self.db, ordem.id_ordem_producao, self.usuario.id_usuario
        )
        producao_service.registrar_consumo(
            self.db,
            ordem.id_ordem_producao,
            insumo.id_item,
            2,
            self.usuario.id_usuario,
        )
        with self.assertRaisesRegex(ValueError, "inspeção final aprovada"):
            producao_service.finalizar_producao(
                self.db, ordem.id_ordem_producao, 2, self.usuario.id_usuario
            )
        producao_service.registrar_inspecao_qualidade(
            self.db,
            ordem.id_ordem_producao,
            "FINAL",
            "APROVADO",
            2,
            2,
            0,
            self.usuario.id_usuario,
        )
        finalizada = producao_service.finalizar_producao(
            self.db, ordem.id_ordem_producao, 2, self.usuario.id_usuario
        )
        self.assertEqual("Finalizado", finalizada.status_ordem)
        self.assertEqual("CONCLUIDO", finalizada.planejamento.status_planejamento)

    def _estrutura_logistica(self):
        cliente = criar_cliente(
            self.db,
            self.usuario,
            "Cliente Logístico",
            "12345678000155",
            rua="Rua das Rotas",
            numero="10",
            cidade="Recife",
            uf="PE",
        )
        produto = criar_item(
            self.db,
            self.usuario,
            "Produto para entrega",
            "UN",
            "PRODUTO_ACABADO",
            saldo_inicial=10,
            preco_venda=50,
        )
        pedido = criar_pedido_venda(
            self.db,
            cliente.id_cliente,
            [{"id_item": produto.id_item, "quantidade": 2, "valor_unitario": 50}],
            self.usuario,
        )
        entrega = criar_entrega_para_pedido(
            self.db, pedido.id_pedido_venda, date.today() + timedelta(days=2)
        )
        return produto, pedido, entrega

    def test_rota_rastreamento_comprovante_e_devolucao(self):
        produto, pedido, entrega = self._estrutura_logistica()
        referencia = configurar_rastreamento_externo(
            self.db,
            entrega.id_entrega,
            "BR123",
            self.usuario.id_usuario,
            "Transportadora Teste",
            "https://example.com/BR123",
        )
        self.assertEqual("BR123", referencia.codigo_rastreio)
        veiculo = criar_veiculo(
            self.db,
            "ABC1D23",
            "Van",
            100,
            self.usuario.id_usuario,
            "Motorista Teste",
        )
        rota = criar_rota_entrega(
            self.db,
            "Rota Recife",
            date.today(),
            veiculo.id_veiculo,
            [{"id_entrega": entrega.id_entrega, "peso_estimado_kg": 20}],
            self.usuario.id_usuario,
        )
        iniciar_rota(self.db, rota.id_rota, self.usuario.id_usuario)
        self.assertEqual("Em rota", entrega.status_logistica)
        registrar_evento_rastreamento(
            self.db,
            entrega.id_entrega,
            "Tentativa de entrega",
            self.usuario.id_usuario,
            "Cliente ausente",
            "Recife/PE",
        )
        comprovante = registrar_comprovante_entrega(
            self.db,
            entrega.id_entrega,
            "Maria Cliente",
            "Maria Cliente",
            self.usuario.id_usuario,
            conteudo_arquivo=b"comprovante-teste",
            nome_arquivo="comprovante.txt",
            tipo_arquivo="text/plain",
        )
        self.assertEqual(64, len(comprovante.hash_arquivo))
        self.assertEqual("Entregue", entrega.status_logistica)
        self.assertEqual("Concluído", pedido.status_venda)
        finalizar_rota(self.db, rota.id_rota, self.usuario.id_usuario)

        devolucao = solicitar_devolucao(
            self.db,
            entrega.id_entrega,
            "Produto incompatível",
            [
                {
                    "id_item": produto.id_item,
                    "quantidade": 2,
                    "condicao_item": "INTEGRO",
                    "reintegrar_estoque": True,
                }
            ],
            self.usuario.id_usuario,
        )
        receber_devolucao(self.db, devolucao.id_devolucao, self.usuario.id_usuario)
        self.assertEqual(Decimal("10.00"), self.db.get(Item, produto.id_item).saldo_estoque)
        self.assertEqual("Devolvido", entrega.status_logistica)
        self.assertEqual("Devolvido", pedido.status_venda)
        self.assertGreaterEqual(self.db.query(EventoRastreamentoEntrega).count(), 5)
        self.assertEqual(1, self.db.query(ComprovanteEntrega).count())

    def test_rota_bloqueia_peso_acima_da_capacidade(self):
        _, _, entrega = self._estrutura_logistica()
        veiculo = criar_veiculo(
            self.db, "DEF4G56", "Utilitário", 10, self.usuario.id_usuario
        )
        with self.assertRaisesRegex(ValueError, "excede a capacidade"):
            criar_rota_entrega(
                self.db,
                "Rota acima do peso",
                date.today(),
                veiculo.id_veiculo,
                [{"id_entrega": entrega.id_entrega, "peso_estimado_kg": 11}],
                self.usuario.id_usuario,
            )


if __name__ == "__main__":
    unittest.main()
