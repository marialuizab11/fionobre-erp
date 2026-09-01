import streamlit as st
import pandas as pd
from datetime import date, timedelta
from src.database.models.producao import CentroProducao
from src.services.producao_service import consultar_carga_centros, listar_ordens_producao


def render_bi_producao(db, usuario_atual):
    st.markdown("### Visão de PCP e Produção")
    st.caption(
        "Acompanhe a carga horária e a taxa de ocupação dos centros produtivos, "
        "o status das ordens de fabricação e o volume de entregas programadas."
    )

    hoje = date.today()
    col_inicio, col_fim, _ = st.columns([1, 1, 2])
    data_inicio = col_inicio.date_input(
        "Data inicial", hoje - timedelta(days=7), key="bi_pcp_inicio", format="DD/MM/YYYY"
    )
    data_fim = col_fim.date_input(
        "Data final", hoje + timedelta(days=14), key="bi_pcp_fim", format="DD/MM/YYYY"
    )

    if data_inicio > data_fim:
        st.warning("A data inicial deve ser anterior ou igual à data final.")
        return

    st.markdown("---")
    st.markdown("#### Ocupação e Carga dos Centros de Produção")
    
    carga = consultar_carga_centros(db, data_inicio, data_fim)
    if carga:
        df_carga = pd.DataFrame([
            {
                "Data": item["data"].strftime("%d/%m/%Y"),
                "Centro": item["centro"],
                "Capacidade (h)": float(item["capacidade"]),
                "Alocado (h)": float(item["alocado"]),
                "Disponível (h)": float(item["disponivel"]),
                "Ocupação (%)": float(item["ocupacao_percentual"]),
            }
            for item in carga
        ])
        
        # Gráfico de ocupação percentual por centro e data
        st.vega_lite_chart(df_carga, {
            "mark": {"type": "bar", "cornerRadiusTopLeft": 3, "cornerRadiusTopRight": 3},
            "encoding": {
                "x": {"field": "Data", "type": "nominal", "title": "Data"},
                "y": {"field": "Ocupação (%)", "type": "quantitative", "title": "Ocupação (%)"},
                "color": {
                    "field": "Centro", 
                    "type": "nominal",
                    "scale": {"range": ["#2E7D32", "#7CB342", "#C0CA33", "#81C784"]}
                },
                "tooltip": [
                    {"field": "Centro", "type": "nominal"},
                    {"field": "Data", "type": "nominal"},
                    {"field": "Ocupação (%)", "type": "quantitative", "format": ".1f"},
                    {"field": "Alocado (h)", "type": "quantitative", "format": ".2f"}
                ]
            }
        }, use_container_width=True)

        st.dataframe(df_carga, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma capacidade alocada no período selecionado.")

    st.markdown("---")
    st.markdown("#### Status Geral das Ordens de Produção")
    
    ordens = listar_ordens_producao(db)
    if not ordens:
        st.info("Nenhuma ordem de produção cadastrada para gerar indicadores.")
        return

    total_ordens = len(ordens)
    concluidas = sum(1 for o in ordens if o.status_ordem == "Finalizado")
    em_andamento = sum(1 for o in ordens if o.status_ordem == "Em Producao")
    criadas = sum(1 for o in ordens if o.status_ordem == "Criado")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de Ordens", total_ordens)
    c2.metric("Criadas / Planejadas", criadas)
    c3.metric("Em Fabricação", em_andamento)
    c4.metric("Finalizadas", concluidas)

    dados_status = pd.DataFrame([
        {"Status": "Criado", "Quantidade": criadas},
        {"Status": "Em Produção", "Quantidade": em_andamento},
        {"Status": "Finalizado", "Quantidade": concluidas},
    ])

    st.vega_lite_chart(dados_status, {
        "mark": {"type": "bar"},
        "encoding": {
            "x": {"field": "Status", "type": "nominal", "title": "Status da Ordem"},
            "y": {"field": "Quantidade", "type": "quantitative", "title": "Total de Ordens"},
            "color": {
                "field": "Status", 
                "type": "nominal",
                "scale": {"domain": ["Criado", "Em Produção", "Finalizado"], "range": ["#FFA000", "#1E88E5", "#2E7D32"]}
            }
        }
    }, use_container_width=True)