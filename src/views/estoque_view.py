import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from src.database.connection import SessionLocal
from src.database.models.cadastros import Item
from src.database.models.estoque import LocalizacaoEstoque
from src.database.models.core import MovimentacaoEstoque
from src.services.bi_suprimentos_service import (
    calcular_indicadores_suprimentos,
    calcular_necessidades_reposicao,
)
from src.services.estoque_service import transferir_estoque, ajustar_estoque_manual
from src.views.components.ui_components import render_cabecalho


def _formatar_reais(valor):
    formatado = f"{float(valor):,.2f}"
    return f"R$ {formatado.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def _render_bi_suprimentos(db):
    st.markdown("### Visão de Suprimentos e Estoque")
    st.caption(
        "Acompanhe o capital imobilizado, as rupturas e as aquisições confirmadas "
        "ou recebidas no período."
    )

    hoje = date.today()
    col_inicio, col_fim, _ = st.columns([1, 1, 2])
    data_inicio = col_inicio.date_input(
        "Data inicial", hoje - timedelta(days=30), key="bi_suprimentos_inicio"
    )
    data_fim = col_fim.date_input(
        "Data final", hoje, key="bi_suprimentos_fim"
    )

    if data_inicio > data_fim:
        st.warning("A data inicial deve ser anterior ou igual à data final.")
        return

    indicadores = calcular_indicadores_suprimentos(db, data_inicio, data_fim)
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Valor Imobilizado em Estoque",
        _formatar_reais(indicadores.valor_imobilizado),
        help="Soma do saldo atual multiplicado pelo custo médio de cada item.",
    )
    col2.metric(
        "Itens em Ruptura",
        indicadores.itens_em_ruptura,
        help="Itens com saldo atual abaixo do estoque mínimo configurado.",
    )
    col3.metric(
        "Custo Total de Aquisição",
        _formatar_reais(indicadores.custo_total_aquisicao),
        help="Pedidos confirmados ou recebidos cuja data do pedido está no período.",
    )

    st.markdown("#### Distribuição do valor em estoque por tipo de item")
    if not indicadores.valor_por_tipo:
        st.info("Não há valor em estoque para exibir no gráfico.")
    else:
        dados_grafico = pd.DataFrame(indicadores.valor_por_tipo)
        st.vega_lite_chart(
            dados_grafico,
            {
                "mark": {"type": "arc", "innerRadius": 65},
                "encoding": {
                    "theta": {
                        "field": "Valor em estoque",
                        "type": "quantitative",
                        "stack": True,
                    },
                    "color": {
                        "field": "Tipo de item",
                        "type": "nominal",
                        "legend": {"title": "Tipo de item", "orient": "right"},
                        "scale": {"range": ["#2E7D32", "#7CB342", "#C0CA33"]},
                    },
                    "tooltip": [
                        {"field": "Tipo de item", "type": "nominal"},
                        {
                            "field": "Valor em estoque",
                            "type": "quantitative",
                            "format": ",.2f",
                            "title": "Valor (R$)",
                        },
                    ],
                },
                "view": {"stroke": None},
            },
            use_container_width=True,
        )

    st.markdown("#### Necessidades de reposição")
    st.caption(
        "Sugestão = estoque mínimo − saldo atual − quantidades em pedidos "
        "criados ou confirmados."
    )
    necessidades = calcular_necessidades_reposicao(db)
    if not necessidades:
        st.info("Nenhum item cadastrado para analisar.")
        return

    tipos = sorted({registro["Tipo"] for registro in necessidades})
    col_situacao, col_tipo, col_resumo = st.columns([1, 1, 2])
    filtro_situacao = col_situacao.selectbox(
        "Situação",
        [
            "Com necessidade de compra",
            "Todos",
            "Em ruptura",
            "Compra em andamento",
            "Normal",
        ],
        key="bi_reposicao_situacao",
    )
    filtro_tipo = col_tipo.selectbox(
        "Tipo de item", ["Todos", *tipos], key="bi_reposicao_tipo"
    )

    if filtro_situacao == "Com necessidade de compra":
        filtradas = [r for r in necessidades if r["Sugestão de compra"] > 0]
    elif filtro_situacao == "Em ruptura":
        filtradas = [r for r in necessidades if r["Saldo atual"] < r["Estoque mínimo"]]
    elif filtro_situacao == "Todos":
        filtradas = necessidades
    else:
        filtradas = [r for r in necessidades if r["Situação"] == filtro_situacao]

    if filtro_tipo != "Todos":
        filtradas = [r for r in filtradas if r["Tipo"] == filtro_tipo]

    itens_para_comprar = sum(r["Sugestão de compra"] > 0 for r in necessidades)
    col_resumo.metric("Itens com compra sugerida", itens_para_comprar)

    if not filtradas:
        st.info("Nenhum item corresponde aos filtros selecionados.")
        return

    st.dataframe(
        pd.DataFrame(filtradas),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Saldo atual": st.column_config.NumberColumn(format="%.2f"),
            "Estoque mínimo": st.column_config.NumberColumn(format="%.2f"),
            "Em compra": st.column_config.NumberColumn(format="%.2f"),
            "Sugestão de compra": st.column_config.NumberColumn(format="%.2f"),
        },
    )


def render_estoque(usuario_atual):
    render_cabecalho("Painel de Estoque", "Gerencie saldos, localizações e movimentações.")
    
    if "sucesso_estoque_msg" in st.session_state:
        st.toast(st.session_state["sucesso_estoque_msg"], icon="✅")
        del st.session_state["sucesso_estoque_msg"]

    db = SessionLocal()
    try:
        tab_visao, tab_bi, tab_locais, tab_mov = st.tabs([
            "Visão Geral",
            "BI de Suprimentos",
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

        with tab_bi:
            _render_bi_suprimentos(db)

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
                                    ajustar_estoque_manual(db, item_ajuste.id_item, local_ajuste.id_localizacao, qtd_ajuste, usuario_atual.id_usuario, obs_ajuste)
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
                                    transferir_estoque(db, item_transf.id_item, qtd_transf, loc_origem.id_localizacao, loc_destino.id_localizacao, usuario_atual.id_usuario, obs_transf)
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
                    nome_usuario = m.usuario.nome if getattr(m, 'usuario', None) else f"ID {m.id_usuario}"
                    
                    dados_mov.append({
                        "Data": m.data_movimento.strftime('%d/%m/%Y %H:%M') if m.data_movimento else "-",
                        "Tipo": m.tipo_movimento,
                        "Item": m.item.descricao if m.item else f"ID {m.id_item}",
                        "Qtd": float(m.quantidade),
                        "Origem": m.local_origem.nome if getattr(m, 'local_origem', None) else "-",
                        "Destino": m.local_destino.nome if getattr(m, 'local_destino', None) else "-",
                        "Usuário": nome_usuario,
                        "Observação": m.observacao or "-"
                    })
                st.dataframe(pd.DataFrame(dados_mov), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Erro ao carregar o painel de estoque: {e}")
    finally:
        db.close()
