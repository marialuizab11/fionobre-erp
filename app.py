import os
import sys

import streamlit as st

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.connection import init_db
from src.views.admin_view import render_admin
from src.views.auth_view import exigir_login_google, render_usuario_sidebar
from src.views.cadastros_view import render_cadastros
from src.views.components.ui_components import aplicar_estilo_global
from src.views.compras_view import render_compras
from src.views.estoque_view import render_estoque
from src.views.inventario_view import render_inventario
from src.views.financeiro_view import render_financeiro
from src.views.gestao_vendas_view import render_gestao_vendas
from src.views.logistica_view import render_logistica
from src.views.producao_view import render_producao
from src.views.vendas_view import render_vendas


@st.cache_resource
def preparar_banco():
    init_db()


def main():
    st.set_page_config(
        page_title="FioNobre ERP - Gestao Industrial",
        page_icon="🧵",
        layout="wide",
    )
    aplicar_estilo_global()
    preparar_banco()
    usuario_atual = exigir_login_google()

    st.sidebar.markdown("## 🧵 FioNobre ERP")
    st.sidebar.markdown("### Menu Operacional")

    rotas_possiveis = {}
    if usuario_atual.pode("cadastros.gerenciar"):
        rotas_possiveis["Cadastros"] = lambda: render_cadastros(usuario_atual)
    if usuario_atual.pode("estoque.visualizar"):
        rotas_possiveis["Controle de Estoque"] = lambda: render_estoque(usuario_atual)
        rotas_possiveis["Inventário Físico"] = lambda: render_inventario(usuario_atual)
    if usuario_atual.pode("compras.gerenciar"):
        rotas_possiveis["Compras"] = lambda: render_compras(usuario_atual)
    if usuario_atual.pode("producao.gerenciar"):
        rotas_possiveis["PCP e Producao"] = lambda: render_producao(usuario_atual)
    if usuario_atual.pode("vendas.gerenciar"):
        rotas_possiveis["Pedidos de Venda"] = lambda: render_vendas(usuario_atual)
        rotas_possiveis["Gestao de Vendas"] = lambda: render_gestao_vendas(usuario_atual)
    if usuario_atual.pode("financeiro.gerenciar"):
        rotas_possiveis["Financeiro"] = lambda: render_financeiro(usuario_atual)
    if usuario_atual.pode("logistica.gerenciar"):
        rotas_possiveis["Gestao Logistica"] = render_logistica
    if usuario_atual.pode("usuarios.gerenciar") or usuario_atual.pode("auditoria.visualizar"):
        rotas_possiveis["Administracao"] = lambda: render_admin(usuario_atual)

    if not rotas_possiveis:
        st.error("Seu perfil nao possui acesso a nenhum modulo.")
        st.stop()

    pagina_selecionada = st.sidebar.radio("Navegar para:", list(rotas_possiveis))
    st.sidebar.markdown("---")
    render_usuario_sidebar(usuario_atual)
    
    rotas_possiveis[pagina_selecionada]()


if __name__ == "__main__":
    main()