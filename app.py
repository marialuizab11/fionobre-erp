import sys
import os
import streamlit as st

from src.views.estoque_view import render_estoque

# Garante o path para importar o backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.views.components.ui_components import aplicar_estilo_global, render_cabecalho
from src.views.auth_view import exigir_login_google, render_usuario_sidebar
from src.views.admin_view import render_admin

# Configuração da Página
st.set_page_config(
    page_title="FioNobre ERP - Gestão Industrial",
    page_icon="🧵",
    layout="wide"
)

# Aplica o tema visual
aplicar_estilo_global()

# Autenticação Google e autorização local por perfil
usuario_atual = exigir_login_google()

# Sidebar de Navegação
st.sidebar.image("https://via.placeholder.com/150x50/E3EDF7/2E7D32?text=FioNobre+ERP", use_container_width=True) # Espaço reservado para a logo
st.sidebar.markdown("### Menu Operacional")

paginas_permitidas = []
if usuario_atual.pode("estoque.visualizar"):
    paginas_permitidas.append("📦 Controle de Estoque")
if usuario_atual.pode("vendas.gerenciar"):
    paginas_permitidas.append("🛒 Pedidos de Venda")
if usuario_atual.pode("logistica.gerenciar"):
    paginas_permitidas.append("🚚 Gestão Logística")
if usuario_atual.pode("usuarios.gerenciar") or usuario_atual.pode("auditoria.visualizar"):
    paginas_permitidas.append("🔐 Administração")

if not paginas_permitidas:
    st.error("Seu perfil não possui acesso a nenhum módulo.")
    st.stop()

pagina = st.sidebar.radio("Navegar para:", paginas_permitidas)

st.sidebar.markdown("---")
st.sidebar.info("Sistema integrado de apoio à decisão (2026.1).")
render_usuario_sidebar(usuario_atual)

# Roteamento de Páginas
if pagina == "📦 Controle de Estoque":
    render_estoque()

elif pagina == "🛒 Pedidos de Venda":
    render_cabecalho("Central de Vendas", "Lance novos pedidos e dispare a baixa automática de estoque.")
    st.write("*(Aqui carregaremos o formulário de vendas em breve)*")

elif pagina == "🚚 Gestão Logística":
    render_cabecalho("Painel Logístico", "Monitore o status das entregas, fretes e prazos.")
    st.write("*(Aqui carregaremos o painel de transportes em breve)*")

elif pagina == "🔐 Administração":
    render_admin(usuario_atual)
