import streamlit as st
import pandas as pd
from datetime import date
from decimal import Decimal

from src.database.connection import SessionLocal
from src.services.financeiro_service import (
    calcular_fluxo_caixa,
    calcular_visao_financeira,
)

def _moeda(valor) -> str:
    texto = f"{Decimal(valor):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")

def render_bi_financeiro(db, usuario_atual):
    st.markdown("### Visão Financeira")
    st.caption("Acompanhe a liquidez, o saldo projetado, o índice de inadimplência e o comportamento do fluxo de caixa.")

    hoje = date.today()
    
    st.markdown("#### Filtros e Parametrização")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
        data_inicio = st.date_input(
            "Data Inicial", hoje.replace(day=1), key="bi_fin_inicio_novo", format="DD/MM/YYYY"
        )
    with col_f2:
        data_fim = st.date_input(
            "Data Final", hoje, key="bi_fin_fim_novo", format="DD/MM/YYYY"
        )
    with col_f3:
        incluir_pendentes = st.checkbox("Incluir Projeções Pendentes", value=True, key="bi_fin_pendentes")
    with col_f4:
        agrupamento = st.selectbox("Agrupamento Temporal", ["Diário", "Mensal"], key="bi_fin_agrup")

    if data_inicio > data_fim:
        st.error("A data inicial não pode ser posterior à data final.")
        return

    visao = calcular_visao_financeira(db, data_inicio, data_fim)
    realizado = calcular_fluxo_caixa(db, data_inicio, data_fim)
    projetado = calcular_fluxo_caixa(db, data_inicio, data_fim, incluir_pendentes=True)

    st.markdown("---")
    st.markdown("#### Indicadores-Chave de Desempenho (KPIs)")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Saldo Projetado", _moeda(visao["saldo_projetado"]), help="Saldo final considerando recebimentos e pagamentos projetados.")
    k2.metric("Inadimplência", _moeda(visao["inadimplencia"]), help="Total de títulos vencidos e não pagos.")
    k3.metric("Títulos em Atraso", visao["qtd_titulos_atrasados"])
    k4.metric("Caixa Realizado (Saldo)", _moeda(realizado["saldo"]), help="Entradas menos saídas efetivamente baixadas no período.")

    st.markdown("---")
    st.markdown("#### Resumo Consolidado de Contas")
    c_e1, c_e2, c_e3, c_e4 = st.columns(4)
    c_e1.metric("Entradas Realizadas", _moeda(realizado["total_entradas"]))
    c_e2.metric("Saídas Realizadas", _moeda(realizado["total_saidas"]))
    c_e3.metric("Contas a Receber Pendentes", _moeda(visao["total_receber_pendente"]))
    c_e4.metric("Contas a Pagar Pendentes", _moeda(visao["total_pagar_pendente"]))

    movimentos_alvo = projetado["movimentos"] if incluir_pendentes else realizado["movimentos"]
    
    if movimentos_alvo:
        st.markdown("---")
        if agrupamento == "Diário":
            st.markdown("#### Evolução Diária do Fluxo de Caixa")
            diario = {}
            for movimento in movimentos_alvo:
                dia = movimento["data"].date()
                valores = diario.setdefault(
                    dia, {"Data": dia, "Entradas": 0.0, "Saídas": 0.0}
                )
                valores["Entradas"] += float(movimento["entrada"])
                valores["Saídas"] += float(movimento["saida"])
            
            df_diario = pd.DataFrame(diario.values()).set_index("Data")
            st.bar_chart(df_diario[["Entradas", "Saídas"]], color=["#2E7D32", "#81C784"])
        else:
            st.markdown("#### Evolução Mensal do Fluxo de Caixa")
            serie = visao["serie_mensal"]
            if serie:
                df_serie = pd.DataFrame(
                    [
                        {
                            "Mês": item["label"],
                            "Entradas": float(item["entradas"]),
                            "Saídas": float(item["saidas"]),
                        }
                        for item in serie
                    ]
                ).set_index("Mês")
                st.bar_chart(df_serie, color=["#2E7D32", "#81C784"])

        with st.expander("Ver detalhamento tabular das movimentações"):
            st.dataframe(
                [
                    {
                        "Data": item["data"].strftime("%d/%m/%Y"),
                        "Descrição": item["descricao"],
                        "Categoria": item["categoria"],
                        "Entrada (R$)": float(item["entrada"]),
                        "Saída (R$)": float(item["saida"]),
                        "Saldo Acumulado (R$)": float(item["saldo"]),
                    }
                    for item in movimentos_alvo
                ],
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("Não há movimentações financeiras registradas para os filtros selecionados.")
