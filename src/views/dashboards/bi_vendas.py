import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from src.services.venda_service import listar_pedidos
from src.services.dashboard_venda_service import (
    obter_kpis_comerciais,
    obter_top_5_produtos,
    obter_curva_abc_produtos
)

def render_bi_vendas(db, usuario_atual):
    st.markdown("### Visão Comercial")

    st.markdown("#### Filtros Gerenciais")
    col_d1, col_d2, col_d3, col_d4 = st.columns([1, 1, 1, 1])
    
    with col_d1:
        data_inicio = st.date_input(
            "Data Inicial", 
            value=datetime.today().date() - timedelta(days=30),
            format="DD/MM/YYYY"
        )
    with col_d2:
        data_fim = st.date_input(
            "Data Final", 
            value=datetime.today().date(),
            format="DD/MM/YYYY"
        )
        
    if data_inicio > data_fim:
        st.error("A data inicial não pode ser maior que a final.")
        return

    dt_inicio_full = datetime.combine(data_inicio, datetime.min.time())
    dt_fim_full = datetime.combine(data_fim, datetime.max.time())
    
    pedidos_brutos = listar_pedidos(db=db, data_inicio=dt_inicio_full, data_fim=dt_fim_full)
    pedidos_lista = pedidos_brutos if isinstance(pedidos_brutos, list) else []
    dados_top5 = obter_top_5_produtos(db, dt_inicio_full, dt_fim_full)
    
    clientes_unicos = ["Todos"] + sorted(list(set(p.cliente.razao_social for p in pedidos_lista if getattr(p, 'cliente', None))))
    status_unicos = ["Todos"] + sorted(list(set(p.status_venda for p in pedidos_lista if p.status_venda)))

    with col_d3:
        filtro_cli = st.selectbox("Cliente", options=clientes_unicos)
    with col_d4:
        filtro_stat = st.selectbox("Status", options=status_unicos)

    pedidos_filtrados = pedidos_lista
    if filtro_cli != "Todos":
        pedidos_filtrados = [p for p in pedidos_filtrados if getattr(p, 'cliente', None) and p.cliente.razao_social == filtro_cli]
    if filtro_stat != "Todos":
        pedidos_filtrados = [p for p in pedidos_filtrados if p.status_venda == filtro_stat]

    st.markdown("---")
    
    if filtro_cli == "Todos" and filtro_stat == "Todos":
        kpis = obter_kpis_comerciais(db, dt_inicio_full, dt_fim_full)
        fat_exibicao = kpis['faturamento_bruto']
        tkt_exibicao = kpis['ticket_medio']
        conv_exibicao = kpis['taxa_conversao']
    else:
        vendas_validas = [p for p in pedidos_filtrados if p.status_venda not in ["Orcamento", "Cancelado"]]
        orc_total = [p for p in pedidos_filtrados if p.status_venda == "Orcamento"]
        fat_exibicao = sum(float(p.valor_total_pedido or 0) for p in vendas_validas)
        tkt_exibicao = fat_exibicao / len(vendas_validas) if vendas_validas else 0
        conv_exibicao = (len(vendas_validas) / (len(vendas_validas) + len(orc_total)) * 100) if (len(vendas_validas) + len(orc_total)) > 0 else 0

    col1, col2, col3 = st.columns(3)
    fat_formatado = f"R$ {fat_exibicao:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    col1.metric(label="Faturamento Filtrado", value=fat_formatado)
    
    tkt_formatado = f"R$ {tkt_exibicao:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    col2.metric(label="Ticket Médio", value=tkt_formatado)
    
    col3.metric(
        label="Taxa de Conversão",
        value=f"{conv_exibicao:.1f} %",
    )

    st.markdown("---")
    
    if not pedidos_filtrados:
        st.info("Nenhum dado encontrado para os filtros selecionados.")
    else:
        dados_df = []
        for p in pedidos_filtrados:
            dados_df.append({
                "data": p.data_venda.strftime('%d/%m/%Y'),
                "valor": float(p.valor_total_pedido or 0),
                "status": p.status_venda,
                "cliente": p.cliente.razao_social if getattr(p, 'cliente', None) else "Desconhecido"
            })
        df_pedidos_bi = pd.DataFrame(dados_df)

        col_grafico1, col_grafico2 = st.columns(2)
        
        with col_grafico1:
            st.write("**Evolução de Entradas (Faturamento Diário)**")
            df_fat_diario = df_pedidos_bi[df_pedidos_bi["status"].isin(["Confirmado", "Concluído"])]
            if not df_fat_diario.empty:
                df_agrupado = df_fat_diario.groupby("data")["valor"].sum().reset_index()
                df_agrupado.set_index("data", inplace=True)
                st.line_chart(df_agrupado, use_container_width=True, color="#2E7D32")
            else:
                st.caption("Sem vendas confirmadas no período para gerar o gráfico.")

        with col_grafico2:
            st.write("**Top 5 Produtos Mais Vendidos**")
            if not dados_top5:
                st.info("Não há dados de saída para o período selecionado.")
            else:
                df_top5 = pd.DataFrame(dados_top5)
                df_top5.set_index("produto", inplace=True)
                st.bar_chart(df_top5["quantidade"], use_container_width=True, color="#7CB342")

        st.markdown("---")
        
        col_grafico3, col_grafico4 = st.columns(2)
        
        with col_grafico3:
            if filtro_cli == "Todos":
                st.write("**Top Clientes (Volume R$)**")
                df_cli_agrupado = df_pedidos_bi[df_pedidos_bi["status"].isin(["Confirmado", "Concluído"])]
                if not df_cli_agrupado.empty:
                    top_clientes = df_cli_agrupado.groupby("cliente")["valor"].sum().nlargest(5).reset_index()
                    top_clientes.set_index("cliente", inplace=True)
                    st.bar_chart(top_clientes, use_container_width=True, color="#1E88E5")
                else:
                    st.caption("Sem dados suficientes.")
            else:
                st.write("**Status dos Pedidos deste Cliente (Qtd)**")
                contagem_status = df_pedidos_bi.groupby("status").size().reset_index(name='quantidade')
                contagem_status.set_index("status", inplace=True)
                st.bar_chart(contagem_status, use_container_width=True, color="#FFA000")
                
        with col_grafico4:
            st.write("**Proporção de Status Geral (Qtd)**")
            contagem_geral = df_pedidos_bi.groupby("status").size().reset_index(name='quantidade')
            contagem_geral.set_index("status", inplace=True)
            st.bar_chart(contagem_geral, use_container_width=True, color="#8E24AA")
            
    st.markdown("---")
    
    st.markdown("#### Curva ABC de Produtos (Pareto)")
    st.caption(
        "Identificação estratégica do impacto na receita: **A** (até 80% do faturamento), "
        "**B** (entre 80% e 95%), e **C** (acima de 95%). "
        "Foque o controle de estoque de segurança nos itens de Classe A."
    )
    
    dados_abc = obter_curva_abc_produtos(db, dt_inicio_full, dt_fim_full)
    
    if not dados_abc:
        st.info("Nenhuma venda confirmada no período para cálculo da Curva ABC.")
    else:
        df_abc = pd.DataFrame(dados_abc)
        
        st.vega_lite_chart(df_abc, {
            "encoding": {
                "x": {
                    "field": "produto", 
                    "type": "nominal", 
                    "sort": {"field": "receita", "order": "descending"}, 
                    "title": "Produto"
                }
            },
            "layer": [
                {
                    "mark": {"type": "line", "interpolate": "monotone", "color": "#1E88E5"},
                    "encoding": {
                        "y": {"field": "acumulado", "type": "quantitative", "title": "% Acumulado da Receita"}
                    }
                },
                {
                    "mark": {"type": "point", "filled": True, "size": 100},
                    "encoding": {
                        "y": {"field": "acumulado", "type": "quantitative"},
                        "color": {
                            "field": "classe", 
                            "type": "nominal", 
                            "scale": {"domain": ["A", "B", "C"], "range": ["#2E7D32", "#FFA000", "#D32F2F"]},
                            "title": "Classe"
                        },
                        "tooltip": [
                            {"field": "produto", "type": "nominal", "title": "Produto"},
                            {"field": "receita", "type": "quantitative", "title": "Receita (R$)", "format": ",.2f"},
                            {"field": "acumulado", "type": "quantitative", "title": "% Acumulado", "format": ".1f"}
                        ]
                    }
                }
            ]
        }, use_container_width=True)

        df_abc['Receita (R$)'] = df_abc['receita'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        df_abc['% Faturamento'] = df_abc['percentual'].apply(lambda x: f"{x:.2f}%")
        df_abc['% Acumulado'] = df_abc['acumulado'].apply(lambda x: f"{x:.2f}%")
        df_abc.rename(columns={'produto': 'Produto', 'classe': 'Classe'}, inplace=True)
        
        st.dataframe(df_abc[['Produto', 'Classe', 'Receita (R$)', '% Faturamento', '% Acumulado']], use_container_width=True, hide_index=True)