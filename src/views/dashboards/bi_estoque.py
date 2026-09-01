import streamlit as st
import pandas as pd
from datetime import date, timedelta
from sqlalchemy import func, desc
from src.database.models.cadastros import Item
from src.database.models.core import MovimentacaoEstoque
from src.services.bi_suprimentos_service import (
    calcular_indicadores_suprimentos,
    calcular_necessidades_reposicao,
)


def _formatar_reais(valor):
    formatado = f"{float(valor):,.2f}"
    return f"R$ {formatado.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def render_bi_estoque(db, usuario_atual):
    st.markdown("### Visão de Suprimentos e Estoque")
    st.caption(
        "Acompanhe o capital imobilizado, rupturas, Curva ABC de insumos, "
        "dias de autonomia e necessidades de reposição."
    )

    hoje = date.today()
    col_inicio, col_fim, _ = st.columns([1, 1, 2])
    data_inicio = col_inicio.date_input(
        "Data inicial", hoje - timedelta(days=30), key="bi_suprimentos_inicio", format="DD/MM/YYYY"
    )
    data_fim = col_fim.date_input(
        "Data final", hoje, key="bi_suprimentos_fim", format="DD/MM/YYYY"
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

    st.markdown("---")
    st.markdown("**Distribuição do Valor em Estoque por Tipo de Item**")
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

    st.markdown("---")
    st.markdown("**Curva ABC de Estoque (Capital Imobilizado)**")
    st.caption(
        "Classificação dos itens pelo custo total armazenado: "
        "A (até 80% do capital), B (80% a 95%) e C (acima de 95%). "
        "Foque o rigor de auditoria e inventário nos itens de Classe A."
    )

    # Correção: Agrupamento unificado por descrição do item para evitar duplicidades
    itens_db = db.query(
        Item.descricao,
        Item.tipo_item,
        func.sum(Item.saldo_estoque).label("saldo_total"),
        func.avg(Item.custo_medio).label("custo_medio")
    ).group_by(
        Item.descricao, Item.tipo_item
    ).all()

    dados_abc_estoque = []
    for it in itens_db:
        saldo = float(it.saldo_total or 0)
        custo = float(it.custo_medio or 0)
        valor_total_item = saldo * custo
        if valor_total_item > 0:
            dados_abc_estoque.append({
                "produto": it.descricao,
                "tipo": it.tipo_item,
                "saldo": saldo,
                "custo": custo,
                "valor_total": valor_total_item
            })

    if not dados_abc_estoque:
        st.info("Não há itens com saldo e custo cadastrados para calcular a Curva ABC de estoque.")
    else:
        df_abc_est = pd.DataFrame(dados_abc_estoque).sort_values(by="valor_total", ascending=False).reset_index(drop=True)
        soma_total_estoque = df_abc_est["valor_total"].sum()
        
        acumulado = 0.0
        classes = []
        perc_acumulado_lista = []
        perc_fat_lista = []

        for _, row in df_abc_est.iterrows():
            p = (row["valor_total"] / soma_total_estoque) * 100
            acumulado += p
            if acumulado <= 80.0:
                cls = "A"
            elif acumulado <= 95.0:
                cls = "B"
            else:
                cls = "C"
            classes.append(cls)
            perc_acumulado_lista.append(acumulado)
            perc_fat_lista.append(p)

        df_abc_est["classe"] = classes
        df_abc_est["acumulado"] = perc_acumulado_lista
        df_abc_est["percentual"] = perc_fat_lista

        st.vega_lite_chart(df_abc_est, {
            "encoding": {
                "x": {
                    "field": "produto", 
                    "type": "nominal", 
                    "sort": {"field": "valor_total", "order": "descending"}, 
                    "title": "Insumo / Item"
                }
            },
            "layer": [
                {
                    "mark": {"type": "line", "interpolate": "monotone", "color": "#2E7D32"},
                    "encoding": {
                        "y": {"field": "acumulado", "type": "quantitative", "title": "% Acumulado do Capital"}
                    }
                },
                {
                    "mark": {"type": "point", "filled": True, "size": 100},
                    "encoding": {
                        "y": {"field": "acumulado", "type": "quantitative"},
                        "color": {
                            "field": "classe", 
                            "type": "nominal", 
                            "scale": {"domain": ["A", "B", "C"], "range": ["#2E7D32", "#7CB342", "#A5D6A7"]},
                            "title": "Classe"
                        },
                        "tooltip": [
                            {"field": "produto", "type": "nominal", "title": "Item"},
                            {"field": "valor_total", "type": "quantitative", "title": "Valor Imobilizado (R$)", "format": ",.2f"},
                            {"field": "acumulado", "type": "quantitative", "title": "% Acumulado", "format": ".1f"}
                        ]
                    }
                }
            ]
        }, use_container_width=True)

        df_abc_est['Valor Total (R$)'] = df_abc_est['valor_total'].apply(_formatar_reais)
        df_abc_est['% Capital'] = df_abc_est['percentual'].apply(lambda x: f"{x:.2f}%")
        df_abc_est['% Acumulado'] = df_abc_est['acumulado'].apply(lambda x: f"{x:.2f}%")
        df_abc_est.rename(columns={'produto': 'Item', 'classe': 'Classe', 'saldo': 'Saldo Atual'}, inplace=True)
        
        st.dataframe(df_abc_est[['Item', 'Classe', 'Saldo Atual', 'Valor Total (R$)', '% Capital', '% Acumulado']], use_container_width=True, hide_index=True) 

    st.markdown("---")
    st.markdown("**Necessidades de Reposição**")
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