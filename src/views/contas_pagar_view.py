from src.services.financeiro_service import TIPO_PAGAR
from src.views.components.financeiro_components import render_lista_contas
from src.views.components.ui_components import render_cabecalho


def render_contas_pagar(usuario_atual, exibir_cabecalho: bool = True):
    if exibir_cabecalho:
        render_cabecalho(
            "Contas a Pagar",
            "Acompanhe obrigações e registre os pagamentos efetuados.",
        )
    render_lista_contas(TIPO_PAGAR, usuario_atual)
