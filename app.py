import sys
import os
import streamlit as st

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.views.components.ui_components import aplicar_estilo_global
from src.views.estoque_view import render_estoque
from src.views.gestao_vendas_view import render_gestao_vendas
from src.views.logistica_view import render_logistica
from src.views.vendas_view import render_vendas
from src.views.contas_receber_view import render_contas_receber

ROTAS = {
    "Controle de Estoque": render_estoque,
    "Pedidos de Venda": render_vendas,
    "Gestão de Vendas": render_gestao_vendas,
    "Gestão Logística": render_logistica,
    "Contas a Receber": render_contas_receber
}

def main():
    st.set_page_config(
        page_title="FioNobre ERP - Gestão Industrial",
        page_icon="🧵",
        layout="wide"
    )

    aplicar_estilo_global()

    st.sidebar.image("https://via.placeholder.com/150x50/E3EDF7/2E7D32?text=FioNobre+ERP", use_container_width=True)
    st.sidebar.markdown("### Menu Operacional")

    opcoes_menu = list(ROTAS.keys())
    pagina_selecionada = st.sidebar.radio("Navegar para:", opcoes_menu)

    st.sidebar.markdown("---")

    view_function = ROTAS.get(pagina_selecionada)
    if view_function:
        view_function()
    else:
        st.error("Página não encontrada ou em desenvolvimento.")

if __name__ == "__main__":
    main()