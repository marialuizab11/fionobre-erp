import streamlit as st
from src.database.connection import SessionLocal
from src.views.components.ui_components import render_cabecalho

from src.views.dashboards.bi_vendas import render_bi_vendas
from src.views.dashboards.bi_financeiro import render_bi_financeiro
from src.views.dashboards.bi_estoque import render_bi_estoque
from src.views.dashboards.bi_producao import render_bi_producao

def render_dashboards(usuario_atual):
    render_cabecalho("Dashboards e Análises", "Visão estratégica e indicadores de performance do ERP.")
    
    abas_bi = st.tabs([
        "Vendas e Comercial", 
        "Financeiro", 
        "Estoque e Suprimentos",
        "PCP e Produção"
    ])
    
    db = SessionLocal()
    try:
        with abas_bi[0]:
            render_bi_vendas(db, usuario_atual)
            
        with abas_bi[1]:
            render_bi_financeiro(db, usuario_atual)
            
        with abas_bi[2]:
            render_bi_estoque(db, usuario_atual)

        with abas_bi[3]:
            render_bi_producao(db, usuario_atual)
    finally:
        db.close()