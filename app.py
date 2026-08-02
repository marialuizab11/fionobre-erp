import sys
import os
import streamlit as st

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.views.components.ui_components import aplicar_estilo_global
from src.views.auth_view import exigir_login_google, render_usuario_sidebar
from src.views.admin_view import render_admin
from src.views.estoque_view import render_estoque
from src.views.gestao_vendas_view import render_gestao_vendas
from src.views.logistica_view import render_logistica
from src.views.vendas_view import render_vendas
from src.views.contas_receber_view import render_contas_receber

def main():
    st.set_page_config(
        page_title="FioNobre ERP - Gestão Industrial",
        page_icon="🧵",
        layout="wide"
    )

    aplicar_estilo_global()

    usuario_atual = exigir_login_google()

    st.sidebar.image("https://via.placeholder.com/150x50/E3EDF7/2E7D32?text=FioNobre+ERP", use_container_width=True)
    st.sidebar.markdown("### Menu Operacional")

    rotas_possiveis = {}
    
    if usuario_atual.pode("estoque.visualizar"):
        rotas_possiveis["Controle de Estoque"] = render_estoque
        
    if usuario_atual.pode("vendas.gerenciar"):
        rotas_possiveis["Pedidos de Venda"] = render_vendas
        rotas_possiveis["Gestão de Vendas"] = render_gestao_vendas
        rotas_possiveis["Contas a Receber"] = render_contas_receber
        
    if usuario_atual.pode("logistica.gerenciar"):
        rotas_possiveis["Gestão Logística"] = render_logistica
        
    if usuario_atual.pode("usuarios.gerenciar") or usuario_atual.pode("auditoria.visualizar"):
        rotas_possiveis["Administração"] = lambda: render_admin(usuario_atual)

    if not rotas_possiveis:
        st.error("Seu perfil não possui acesso a nenhum módulo.")
        st.stop()

    opcoes_menu = list(rotas_possiveis.keys())
    pagina_selecionada = st.sidebar.radio("Navegar para:", opcoes_menu)

    st.sidebar.markdown("---")
    st.sidebar.info("Sistema integrado de apoio à decisão (2026.1).")
    render_usuario_sidebar(usuario_atual)

    view_function = rotas_possiveis.get(pagina_selecionada)
    if view_function:
        view_function()
    else:
        st.error("Página não encontrada ou em desenvolvimento.")

if __name__ == "__main__":
    main()