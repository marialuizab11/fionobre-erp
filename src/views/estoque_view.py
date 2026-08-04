import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from src.database.connection import SessionLocal
from src.database.models.cadastros import Item
from src.database.models.estoque import LocalizacaoEstoque
from src.database.models.core import MovimentacaoEstoque
from src.services.estoque_service import transferir_estoque, ajustar_estoque_manual
from src.views.components.ui_components import render_cabecalho

def render_estoque(usuario_atual=1):
    render_cabecalho("Painel de Estoque", "Gerencie saldos, localizações e movimentações.")
    
    if "sucesso_estoque_msg" in st.session_state:
        st.toast(st.session_state["sucesso_estoque_msg"], icon="✅")
        del st.session_state["sucesso_estoque_msg"]

    db = SessionLocal()
    try:
        tab_visao, tab_locais, tab_mov = st.tabs([
            "Visão Geral", 
            "Transferências e Ajustes", 
            "Histórico de Movimentações"
        ])

        with tab_visao:
            itens = db.query(Item).all()
            if not itens:
                st.warning("Nenhum item cadastrado no sistema.")
            else:
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
                
                dados_tabela = []
                for item in itens:
                    dados_tabela.append({
                        "ID": item.id_item,
                        "Descrição": item.descricao,
                        "Tipo": item.tipo_item,
                        "Unidade": item.unidade_medida,
                        "Saldo Global": float(item.saldo_estoque),
                        "Estoque Mínimo": float(item.estoque_minimo),
                        "Preço Venda (R$)": float(item.preco_venda),
                        "Custo Médio (R$)": float(item.custo_medio)
                    })
                    
                st.dataframe(pd.DataFrame(dados_tabela), use_container_width=True, hide_index=True)

        with tab_locais:
            locais = db.query(LocalizacaoEstoque).filter(LocalizacaoEstoque.ativo == 'S').all()
            itens_disp = db.query(Item).all()
            
            if not locais:
                st.info("Nenhuma localização cadastrada no banco de dados.")
            elif not itens_disp:
                st.info("Nenhum item cadastrado.")
            else:
                col_ajuste, col_transf = st.columns(2)
                
                with col_ajuste:
                    st.markdown("#### 🔧 Ajuste Manual")
                    with st.form("form_ajuste_estoque"):
                        item_ajuste = st.selectbox("Item", itens_disp, format_func=lambda x: f"{x.id_item} - {x.descricao}", key="ajuste_item")
                        local_ajuste = st.selectbox("Localização", locais, format_func=lambda x: x.nome, key="ajuste_local")
                        
                        qtd_ajuste = st.number_input("Quantidade (+ ou -)", value=0.0, step=1.0, format="%.2f")
                        obs_ajuste = st.text_input("Observação / Motivo", max_chars=100)
                        
                        if st.form_submit_button("Registrar Ajuste", type="primary", use_container_width=True):
                            if qtd_ajuste == 0:
                                st.error("A quantidade não pode ser zero.")
                            else:
                                try:
                                    ajustar_estoque_manual(db, item_ajuste.id_item, local_ajuste.id_localizacao, qtd_ajuste, usuario_atual, obs_ajuste)
                                    st.session_state["sucesso_estoque_msg"] = "Ajuste registrado com sucesso!"
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao registrar ajuste: {e}")

                with col_transf:
                    st.markdown("#### ↔️ Transferência Interna")
                    with st.form("form_transf_estoque"):
                        item_transf = st.selectbox("Item", itens_disp, format_func=lambda x: f"{x.id_item} - {x.descricao}", key="transf_item")
                        loc_origem = st.selectbox("Origem", locais, format_func=lambda x: x.nome, key="transf_origem")
                        loc_destino = st.selectbox("Destino", locais, format_func=lambda x: x.nome, key="transf_destino")
                        
                        qtd_transf = st.number_input("Quantidade a Transferir", min_value=0.01, value=1.0, step=1.0, format="%.2f")
                        obs_transf = st.text_input("Observação", max_chars=100)
                        
                        if st.form_submit_button("Transferir", type="primary", use_container_width=True):
                            if loc_origem.id_localizacao == loc_destino.id_localizacao:
                                st.error("Origem e destino não podem ser iguais.")
                            else:
                                try:
                                    transferir_estoque(db, item_transf.id_item, qtd_transf, loc_origem.id_localizacao, loc_destino.id_localizacao, usuario_atual, obs_transf)
                                    st.session_state["sucesso_estoque_msg"] = "Transferência concluída!"
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro na transferência: {e}")

        with tab_mov:
            st.markdown("### Histórico de Movimentações")
            col_filtro, _ = st.columns([1, 2])
            with col_filtro:
                dias_filtro = st.slider("Filtrar últimos X dias", 1, 90, 30)
                
            data_limite = datetime.utcnow() - timedelta(days=dias_filtro)
            movs = db.query(MovimentacaoEstoque).filter(MovimentacaoEstoque.data_movimento >= data_limite).order_by(MovimentacaoEstoque.data_movimento.desc()).all()
            
            if not movs:
                st.info("Nenhuma movimentação encontrada.")
            else:
                dados_mov = []
                for m in movs:
                    dados_mov.append({
                        "Data": m.data_movimento.strftime('%d/%m/%Y %H:%M') if m.data_movimento else "-",
                        "Tipo": m.tipo_movimento,
                        "Item": m.item.descricao if m.item else f"ID {m.id_item}",
                        "Qtd": float(m.quantidade),
                        "Origem": m.local_origem.nome if getattr(m, 'local_origem', None) else "-",
                        "Destino": m.local_destino.nome if getattr(m, 'local_destino', None) else "-",
                        "Observação": m.observacao or "-"
                    })
                st.dataframe(pd.DataFrame(dados_mov), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Erro ao carregar o painel de estoque: {e}")
    finally:
        db.close()