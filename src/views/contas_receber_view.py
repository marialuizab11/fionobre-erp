from src.services.financeiro_service import TIPO_RECEBER
from src.views.components.financeiro_components import render_lista_contas
from src.views.components.ui_components import render_cabecalho


def render_contas_receber(usuario_atual, exibir_cabecalho: bool = True):
    if exibir_cabecalho:
        render_cabecalho(
            "Contas a Receber",
            "Gerencie os recebimentos e acompanhe contas pendentes ou vencidas.",
        )
    render_lista_contas(TIPO_RECEBER, usuario_atual)
