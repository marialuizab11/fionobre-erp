import streamlit as st
from src.database.connection import SessionLocal
from src.database.models.cadastros import Item
from src.views.components.ui_components import render_cabecalho

def render_estoque():
    render_cabecalho("Painel de Estoque", "Acompanhe o saldo atual e o giro das matérias-primas e produtos.")
    
    db = SessionLocal()
    try:
        # Busca todos os itens no banco de dados
        itens = db.query(Item).all()
        
        if not itens:
            st.warning("Nenhum item cadastrado no sistema.")
            return

        # Métricas rápidas no topo
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Itens", len(itens))
        with col2:
            baixo_estoque = sum(1 for i in itens if i.saldo_estoque <= i.estoque_minimo)
            st.metric("Itens Abaixo do Mínimo", baixo_estoque, delta_color="inverse")
        with col3:
            total_unidades = sum(float(i.saldo_estoque) for i in itens)
            st.metric("Saldo Total em Estoque", f"{total_unidades:.2f}")

        st.markdown("### 📋 Relação de Itens e Insumos")
        
        # Prepara os dados para exibição em tabela amigável
        dados_tabela = []
        for item in itens:
            dados_tabela.append({
                "ID": item.id_item,
                "Descrição": item.descricao,
                "Tipo": item.tipo_item,
                "Unidade": item.unidade_medida,
                "Saldo Atual": float(item.saldo_estoque),
                "Estoque Mínimo": float(item.estoque_minimo),
                "Preço Venda (R$)": float(item.preco_venda),
                "Custo Médio (R$)": float(item.custo_medio)
            })
            
        st.dataframe(dados_tabela, use_container_width=True)
        
    except Exception as e:
        st.error(f"Erro ao carregar dados do estoque: {e}")
    finally:
        db.close()