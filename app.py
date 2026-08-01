import sys
import os
import streamlit as st

from src.views.estoque_view import render_estoque
from src.views.logistica_view import render_logistica
from src.views.vendas_view import render_vendas

# Garante o path para importar o backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.views.components.ui_components import aplicar_estilo_global, render_cabecalho

# Configuração da Página
st.set_page_config(
    page_title="FioNobre ERP - Gestão Industrial",
    page_icon="🧵",
    layout="wide"
)

# Aplica o tema visual
aplicar_estilo_global()

# Sidebar de Navegação
st.sidebar.image("https://via.placeholder.com/150x50/E3EDF7/2E7D32?text=FioNobre+ERP", use_container_width=True) # Espaço reservado para a logo
st.sidebar.markdown("### Menu Operacional")

pagina = st.sidebar.radio(
    "Navegar para:",
    ["📦 Controle de Estoque", "🛒 Pedidos de Venda", "🚚 Gestão Logística"]
)

st.sidebar.markdown("---")
st.sidebar.info("Sistema integrado de apoio à decisão (2026.1).")

# Roteamento de Páginas
if pagina == "📦 Controle de Estoque":
    render_estoque()

elif pagina == "🚚 Gestão Logística":
    render_logistica()

elif pagina == "🛒 Pedidos de Venda":
    render_vendas()