import unittest
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base
import src.database.models.estoque  # noqa: F401 — registra localizacao_estoque
from src.database.models.financeiro import MovimentoExtratoBancario
from src.database.models.usuarios import LogOperacao
from src.services.auth_service import criar_contexto_usuario, sincronizar_usuario_google
from src.services.financeiro_service import (
    STATUS_PAGO,
    calcular_fluxo_caixa,
    calcular_visao_financeira,
    conciliar_movimento,
    criar_lancamento_manual,
    gerar_balancete,
    gerar_dre,
    listar_lancamentos_para_conciliacao,
    registrar_movimento_extrato,
)
from src.services.usuario_service import cadastrar_usuario


def claims_google(sub: str, email: str) -> dict:
    return {
        "sub": sub,
        "email": email,
        "email_verified": True,
        "name": "Usuário Financeiro",
    }


class FinanceiroServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        usuario = sincronizar_usuario_google(
            self.db,
            claims_google("financeiro-admin", "financeiro@example.com"),
            admin_emails={"financeiro@example.com"},
        )
        self.admin = criar_contexto_usuario(usuario)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _lancamento(
        self,
        natureza: str,
        descricao: str,
        categoria: str,
        valor: str,
        pago: bool = False,
    ):
        hoje = date.today()
        return criar_lancamento_manual(
            self.db,
            self.admin,
            natureza,
            descricao,
            categoria,
            valor,
            hoje,
            data_pagamento=hoje if pago else None,
        )

    def test_fluxo_dre_e_balancete_consideram_natureza_e_status(self):
        self._lancamento("RECEITA", "Serviço recebido", "Serviços", "100.00", True)
        self._lancamento(
            "DESPESA", "Material pago", "Compras de materiais", "40.00", True
        )
        self._lancamento(
            "DESPESA", "Imposto a vencer", "Impostos", "20.00", False
        )

        hoje = date.today()
        realizado = calcular_fluxo_caixa(self.db, hoje, hoje)
        projetado = calcular_fluxo_caixa(
            self.db, hoje, hoje, incluir_pendentes=True
        )
        self.assertEqual(Decimal("100.00"), realizado["total_entradas"])
        self.assertEqual(Decimal("40.00"), realizado["total_saidas"])
        self.assertEqual(Decimal("60.00"), realizado["saldo"])
        self.assertEqual(Decimal("40.00"), projetado["saldo"])

        dre_competencia = gerar_dre(self.db, hoje, hoje, "COMPETENCIA")
        dre_caixa = gerar_dre(self.db, hoje, hoje, "CAIXA")
        self.assertEqual(Decimal("60.00"), dre_competencia["total_despesas"])
        self.assertEqual(Decimal("40.00"), dre_caixa["total_despesas"])
        self.assertEqual(Decimal("40.00"), dre_competencia["resultado"])

        balancete = gerar_balancete(self.db, hoje, hoje)
        imposto = next(
            item for item in balancete["linhas"] if item["categoria"] == "Impostos"
        )
        self.assertEqual(Decimal("20.00"), imposto["pendente"])

    def test_visao_financeira_kpi_saldo_projetado_e_inadimplencia(self):
        hoje = date.today()
        criar_lancamento_manual(
            self.db,
            self.admin,
            "RECEITA",
            "Cliente em atraso",
            "Vendas",
            "100.00",
            hoje - timedelta(days=15),
        )
        criar_lancamento_manual(
            self.db,
            self.admin,
            "RECEITA",
            "Cliente no prazo",
            "Vendas",
            "50.00",
            hoje + timedelta(days=10),
        )
        criar_lancamento_manual(
            self.db,
            self.admin,
            "DESPESA",
            "Fornecedor pendente",
            "Compras de materiais",
            "30.00",
            hoje + timedelta(days=5),
        )
        criar_lancamento_manual(
            self.db,
            self.admin,
            "RECEITA",
            "Receita paga no mês",
            "Serviços",
            "200.00",
            hoje,
            data_pagamento=hoje,
        )
        criar_lancamento_manual(
            self.db,
            self.admin,
            "DESPESA",
            "Despesa paga no mês",
            "Impostos",
            "70.00",
            hoje,
            data_pagamento=hoje,
        )

        visao = calcular_visao_financeira(self.db, hoje.replace(day=1), hoje)
        self.assertEqual(Decimal("120.00"), visao["saldo_projetado"])
        self.assertEqual(Decimal("150.00"), visao["total_receber_pendente"])
        self.assertEqual(Decimal("30.00"), visao["total_pagar_pendente"])
        self.assertEqual(Decimal("100.00"), visao["inadimplencia"])
        self.assertEqual(1, visao["qtd_titulos_atrasados"])
        self.assertTrue(visao["serie_mensal"])
        mes_atual = visao["serie_mensal"][-1]
        self.assertGreaterEqual(mes_atual["entradas"], Decimal("200.00"))
        self.assertGreaterEqual(mes_atual["saidas"], Decimal("70.00"))

    def test_conciliacao_baixa_lancamento_e_registra_auditoria(self):
        lancamento = self._lancamento(
            "RECEITA", "Recebimento avulso", "Outras receitas", "150.00"
        )
        movimento = registrar_movimento_extrato(
            self.db,
            self.admin,
            date.today() + timedelta(days=1),
            "PIX do cliente",
            "150.00",
            "PIX-001",
        )

        sugestoes = listar_lancamentos_para_conciliacao(self.db, movimento)
        self.assertEqual([lancamento.id_lancamento], [item.id_lancamento for item in sugestoes])

        conciliado = conciliar_movimento(
            self.db, movimento.id_movimento, lancamento.id_lancamento, self.admin
        )
        self.assertEqual(lancamento.id_lancamento, conciliado.id_lancamento)
        self.assertEqual(STATUS_PAGO, lancamento.status_pagamento)
        self.assertEqual(movimento.data_movimento, lancamento.data_pagamento)
        self.assertEqual(
            1,
            self.db.query(LogOperacao)
            .filter(LogOperacao.acao == "CONCILIAR_EXTRATO")
            .count(),
        )

    def test_conciliacao_rejeita_natureza_bancaria_incompativel(self):
        lancamento = self._lancamento(
            "DESPESA", "Conta de energia", "Despesas administrativas", "90.00"
        )
        entrada = registrar_movimento_extrato(
            self.db, self.admin, date.today(), "Crédito bancário", "90.00"
        )
        with self.assertRaisesRegex(ValueError, "natureza"):
            conciliar_movimento(
                self.db, entrada.id_movimento, lancamento.id_lancamento, self.admin
            )
        self.assertIsNone(
            self.db.get(MovimentoExtratoBancario, entrada.id_movimento).id_lancamento
        )

    def test_visualizador_nao_pode_criar_lancamento_manual(self):
        cadastrar_usuario(
            self.db,
            self.admin,
            "viewer-financeiro@example.com",
            "Visualizador",
        )
        usuario = sincronizar_usuario_google(
            self.db, claims_google("financeiro-viewer", "viewer-financeiro@example.com")
        )
        visualizador = criar_contexto_usuario(usuario)
        with self.assertRaises(PermissionError):
            criar_lancamento_manual(
                self.db,
                visualizador,
                "RECEITA",
                "Sem acesso",
                "Outras receitas",
                "10.00",
                date.today(),
            )


if __name__ == "__main__":
    unittest.main()
