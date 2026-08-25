import csv
import io
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
import streamlit as st

from src.database.connection import SessionLocal
from src.services.financeiro_service import (
    CATEGORIAS_DESPESA,
    CATEGORIAS_RECEITA,
    TIPO_PAGAR,
    calcular_fluxo_caixa,
    calcular_visao_financeira,
    cancelar_lancamento_manual,
    conciliar_movimento,
    criar_lancamento_manual,
    descricao_lancamento,
    gerar_balancete,
    gerar_dre,
    importar_movimentos_extrato,
    listar_lancamentos,
    listar_lancamentos_para_conciliacao,
    listar_movimentos_extrato,
    registrar_movimento_extrato,
)
from src.views.components.ui_components import render_cabecalho
from src.views.contas_pagar_view import render_contas_pagar
from src.views.contas_receber_view import render_contas_receber


def _moeda(valor) -> str:
    texto = f"{Decimal(valor):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _periodo_padrao(chave: str):
    hoje = date.today()
    col1, col2 = st.columns(2)
    inicio = col1.date_input(
        "Data inicial", hoje.replace(day=1), key=f"{chave}_inicio"
    )
    fim = col2.date_input("Data final", hoje, key=f"{chave}_fim")
    if inicio > fim:
        st.error("A data inicial não pode ser posterior à data final.")
        return None, None
    return inicio, fim


def _render_fluxo_caixa():
    st.markdown("### Fluxo de caixa")
    inicio, fim = _periodo_padrao("fluxo")
    if inicio is None:
        return
    db = SessionLocal()
    try:
        realizado = calcular_fluxo_caixa(db, inicio, fim)
        projetado = calcular_fluxo_caixa(db, inicio, fim, incluir_pendentes=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Entradas realizadas", _moeda(realizado["total_entradas"]))
        c2.metric("Saídas realizadas", _moeda(realizado["total_saidas"]))
        c3.metric("Saldo realizado", _moeda(realizado["saldo"]))
        c4.metric("Saldo projetado", _moeda(projetado["saldo"]))

        if realizado["movimentos"]:
            diario = {}
            for movimento in realizado["movimentos"]:
                dia = movimento["data"].date()
                valores = diario.setdefault(
                    dia, {"Data": dia, "Entradas": 0.0, "Saídas": 0.0}
                )
                valores["Entradas"] += float(movimento["entrada"])
                valores["Saídas"] += float(movimento["saida"])
            grafico = pd.DataFrame(diario.values()).set_index("Data")
            st.bar_chart(grafico[["Entradas", "Saídas"]])
            st.dataframe(
                [
                    {
                        "Data": item["data"].strftime("%d/%m/%Y"),
                        "Descrição": item["descricao"],
                        "Categoria": item["categoria"],
                        "Entrada (R$)": float(item["entrada"]),
                        "Saída (R$)": float(item["saida"]),
                        "Saldo acumulado (R$)": float(item["saldo"]),
                    }
                    for item in realizado["movimentos"]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Não há entradas ou saídas realizadas neste período.")
    finally:
        db.close()


def _render_bi_visao_financeira():
    st.markdown("### BI — Visão Financeira (Fluxo de Caixa)")
    st.caption(
        "KPI 7: Saldo Projetado · KPI 8: Inadimplência · "
        "Gráfico mensal Entradas × Saídas."
    )

    hoje = date.today()
    inicio_padrao = date(hoje.year, 1, 1)
    col1, col2 = st.columns(2)
    inicio = col1.date_input(
        "Período do gráfico — início",
        inicio_padrao,
        key="bi_fin_inicio",
    )
    fim = col2.date_input(
        "Período do gráfico — fim",
        hoje,
        key="bi_fin_fim",
    )
    if inicio > fim:
        st.error("A data inicial não pode ser posterior à data final.")
        return

    db = SessionLocal()
    try:
        visao = calcular_visao_financeira(db, inicio, fim)

        k1, k2, k3 = st.columns(3)
        k1.metric("KPI 7 — Saldo Projetado", _moeda(visao["saldo_projetado"]))
        k2.metric("KPI 8 — Inadimplência / Atrasos", _moeda(visao["inadimplencia"]))
        k3.metric("Títulos em atraso", visao["qtd_titulos_atrasados"])

        d1, d2 = st.columns(2)
        d1.metric("Contas a Receber Pendentes", _moeda(visao["total_receber_pendente"]))
        d2.metric("Contas a Pagar Pendentes", _moeda(visao["total_pagar_pendente"]))

        st.markdown("#### Entradas vs Saídas (mês a mês)")
        serie = visao["serie_mensal"]
        if not serie:
            st.info("Não há lançamentos no período selecionado para montar o gráfico.")
        else:
            df = pd.DataFrame(
                [
                    {
                        "Mês": item["label"],
                        "Entradas (Receitas)": float(item["entradas"]),
                        "Saídas (Custos)": float(item["saidas"]),
                    }
                    for item in serie
                ]
            ).set_index("Mês")
            st.bar_chart(df)

            st.dataframe(
                [
                    {
                        "Mês": item["label"],
                        "Entradas (R$)": float(item["entradas"]),
                        "Saídas (R$)": float(item["saidas"]),
                        "Saldo do mês (R$)": float(item["saldo"]),
                    }
                    for item in serie
                ],
                use_container_width=True,
                hide_index=True,
            )

        with st.expander("Apoio à decisão (2VA)"):
            st.markdown(
                """
- **Padrão:** alta inadimplência (KPI 8) comprimindo o saldo projetado (KPI 7).
- **Recomendação:** interromper novas vendas a prazo para clientes com histórico
  de atraso e priorizar cobranças dos títulos vencidos.
                """.strip()
            )
    finally:
        db.close()


def _render_lancamentos_manuais(usuario_atual):
    st.markdown("### Novo lançamento manual")
    natureza = st.radio(
        "Natureza", ["RECEITA", "DESPESA"], horizontal=True, key="manual_natureza"
    )
    categorias = CATEGORIAS_RECEITA if natureza == "RECEITA" else CATEGORIAS_DESPESA
    with st.form("financeiro_lancamento_manual", clear_on_submit=True):
        descricao = st.text_input("Descrição *")
        col1, col2 = st.columns(2)
        categoria = col1.selectbox("Categoria *", categorias)
        valor = col2.number_input("Valor (R$) *", min_value=0.01, step=10.0)
        col3, col4 = st.columns(2)
        vencimento = col3.date_input("Vencimento", date.today())
        ja_pago = col4.checkbox("Já foi pago/recebido")
        data_pagamento = (
            st.date_input("Data do pagamento/recebimento", date.today())
            if ja_pago
            else None
        )
        observacao = st.text_area("Observação")
        salvar = st.form_submit_button("Salvar lançamento", type="primary")
    if salvar:
        db = SessionLocal()
        try:
            criar_lancamento_manual(
                db,
                usuario_atual,
                natureza,
                descricao,
                categoria,
                valor,
                vencimento,
                observacao=observacao,
                data_pagamento=data_pagamento,
            )
            st.success("Lançamento criado com sucesso.")
            st.rerun()
        except Exception as erro:
            st.error(str(erro))
        finally:
            db.close()

    db = SessionLocal()
    try:
        manuais = [
            item
            for item in listar_lancamentos(db, tipo_lancamento=None)
            if item.origem_lancamento == "manual"
        ]
        if not manuais:
            st.info("Nenhum lançamento manual cadastrado.")
            return
        st.markdown("### Lançamentos cadastrados")
        st.dataframe(
            [
                {
                    "ID": item.id_lancamento,
                    "Natureza": (
                        "Receita" if item.tipo_lancamento != TIPO_PAGAR else "Despesa"
                    ),
                    "Descrição": descricao_lancamento(item),
                    "Vencimento": item.data_vencimento.strftime("%d/%m/%Y"),
                    "Valor (R$)": float(item.valor),
                    "Status": item.status_pagamento,
                }
                for item in manuais
            ],
            use_container_width=True,
            hide_index=True,
        )
        cancelaveis = [item for item in manuais if item.status_pagamento == "Pendente"]
        if cancelaveis:
            mapa = {item.id_lancamento: item for item in cancelaveis}
            col1, col2 = st.columns([4, 1])
            id_cancelar = col1.selectbox(
                "Lançamento pendente",
                list(mapa),
                format_func=lambda valor: f"#{valor} — {descricao_lancamento(mapa[valor])}",
            )
            with col2:
                st.write("")
                st.write("")
                cancelar = st.button("Cancelar lançamento", use_container_width=True)
            if cancelar:
                cancelar_lancamento_manual(db, id_cancelar, usuario_atual)
                st.success("Lançamento cancelado.")
                st.rerun()
    except Exception as erro:
        st.error(str(erro))
    finally:
        db.close()


def _render_relatorios():
    inicio, fim = _periodo_padrao("relatorios")
    if inicio is None:
        return
    aba_dre, aba_balancete = st.tabs(["DRE", "Balancete"])
    db = SessionLocal()
    try:
        with aba_dre:
            regime = st.radio(
                "Regime",
                ["COMPETENCIA", "CAIXA"],
                horizontal=True,
                format_func=lambda valor: (
                    "Competência" if valor == "COMPETENCIA" else "Caixa"
                ),
            )
            dre = gerar_dre(db, inicio, fim, regime)
            c1, c2, c3 = st.columns(3)
            c1.metric("Receitas", _moeda(dre["total_receitas"]))
            c2.metric("Despesas", _moeda(dre["total_despesas"]))
            c3.metric("Resultado", _moeda(dre["resultado"]))
            linhas = [
                {
                    "Grupo": "Receita",
                    "Categoria": categoria,
                    "Valor (R$)": float(valor),
                }
                for categoria, valor in dre["receitas"].items()
            ] + [
                {
                    "Grupo": "Despesa",
                    "Categoria": categoria,
                    "Valor (R$)": float(valor),
                }
                for categoria, valor in dre["despesas"].items()
            ]
            if linhas:
                st.dataframe(linhas, use_container_width=True, hide_index=True)
            else:
                st.info("Não há valores para compor a DRE no período.")

        with aba_balancete:
            balancete = gerar_balancete(db, inicio, fim)
            if balancete["linhas"]:
                st.dataframe(
                    [
                        {
                            "Categoria": item["categoria"],
                            "Receitas (R$)": float(item["receitas"]),
                            "Despesas (R$)": float(item["despesas"]),
                            "Pendente (R$)": float(item["pendente"]),
                            "Saldo (R$)": float(item["saldo"]),
                        }
                        for item in balancete["linhas"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("Não há lançamentos no período.")
    finally:
        db.close()


def _parse_data(valor: str) -> date:
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(valor.strip(), formato).date()
        except ValueError:
            pass
    raise ValueError(f"Data inválida no extrato: {valor}")


def _parse_valor(valor: str) -> Decimal:
    texto = valor.strip().replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return Decimal(texto)


def _ler_csv_extrato(arquivo) -> list[dict]:
    conteudo = arquivo.getvalue().decode("utf-8-sig")
    try:
        delimitador = csv.Sniffer().sniff(
            conteudo[:2048], delimiters=";,\t"
        ).delimiter
    except csv.Error:
        delimitador = ";"
    leitor = csv.DictReader(io.StringIO(conteudo), delimiter=delimitador)
    movimentos = []
    for numero, linha_original in enumerate(leitor, start=2):
        linha = {
            str(chave).strip().lower(): valor
            for chave, valor in linha_original.items()
        }
        data_texto = linha.get("data") or linha.get("data_movimento")
        descricao = linha.get("descricao") or linha.get("descrição")
        valor = linha.get("valor")
        if not data_texto or not descricao or not valor:
            raise ValueError(f"Linha {numero}: informe data, descricao e valor.")
        movimentos.append(
            {
                "data_movimento": _parse_data(data_texto),
                "descricao": descricao,
                "valor": _parse_valor(valor),
                "referencia": linha.get("referencia") or linha.get("referência"),
            }
        )
    if not movimentos:
        raise ValueError("O arquivo não contém movimentos.")
    return movimentos


def _render_conciliacao(usuario_atual):
    st.caption(
        "No extrato, use valores positivos para entradas e negativos para saídas. "
        "O CSV deve conter data, descricao, valor e, opcionalmente, referencia."
    )
    aba_csv, aba_manual = st.tabs(["Importar CSV", "Adicionar movimento"])
    with aba_csv:
        arquivo = st.file_uploader("Arquivo de extrato", type=["csv"])
        if arquivo and st.button("Importar extrato", type="primary"):
            db = SessionLocal()
            try:
                movimentos = _ler_csv_extrato(arquivo)
                importar_movimentos_extrato(db, usuario_atual, movimentos)
                st.success(f"{len(movimentos)} movimento(s) importado(s).")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))
            finally:
                db.close()
    with aba_manual:
        with st.form("movimento_extrato_manual", clear_on_submit=True):
            col1, col2 = st.columns(2)
            data_movimento = col1.date_input("Data", date.today())
            valor = col2.number_input("Valor (R$)", value=0.0, step=10.0)
            descricao = st.text_input("Descrição")
            referencia = st.text_input("Referência")
            adicionar = st.form_submit_button("Adicionar", type="primary")
        if adicionar:
            db = SessionLocal()
            try:
                registrar_movimento_extrato(
                    db, usuario_atual, data_movimento, descricao, valor, referencia
                )
                st.success("Movimento bancário adicionado.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))
            finally:
                db.close()

    db = SessionLocal()
    try:
        movimentos = listar_movimentos_extrato(db)
        if movimentos:
            st.markdown("### Movimentos bancários")
            st.dataframe(
                [
                    {
                        "ID": item.id_movimento,
                        "Data": item.data_movimento.strftime("%d/%m/%Y"),
                        "Descrição": item.descricao,
                        "Valor (R$)": float(item.valor),
                        "Referência": item.referencia or "—",
                        "Situação": "Conciliado" if item.id_lancamento else "Pendente",
                        "Lançamento": item.id_lancamento or "—",
                    }
                    for item in movimentos
                ],
                use_container_width=True,
                hide_index=True,
            )
        pendentes = [item for item in movimentos if item.id_lancamento is None]
        if not pendentes:
            st.info("Não há movimentos bancários pendentes de conciliação.")
            return
        mapa_movimentos = {item.id_movimento: item for item in pendentes}
        id_movimento = st.selectbox(
            "Movimento a conciliar",
            list(mapa_movimentos),
            format_func=lambda valor: (
                f"#{valor} — {mapa_movimentos[valor].descricao} — "
                f"{_moeda(mapa_movimentos[valor].valor)}"
            ),
        )
        movimento = mapa_movimentos[id_movimento]
        sugestoes = listar_lancamentos_para_conciliacao(db, movimento)
        candidatos = sugestoes or listar_lancamentos_para_conciliacao(db)
        if not candidatos:
            st.warning("Não há lançamentos financeiros disponíveis para conciliar.")
            return
        if sugestoes:
            st.success("Foram encontradas sugestões por valor, natureza e proximidade da data.")
        else:
            st.warning("Nenhuma correspondência exata; exibindo os demais lançamentos.")
        mapa_lancamentos = {item.id_lancamento: item for item in candidatos}
        id_lancamento = st.selectbox(
            "Lançamento do sistema",
            list(mapa_lancamentos),
            format_func=lambda valor: (
                f"#{valor} — {descricao_lancamento(mapa_lancamentos[valor])} — "
                f"{_moeda(mapa_lancamentos[valor].valor)}"
            ),
        )
        if st.button("Conciliar", type="primary"):
            try:
                conciliar_movimento(db, id_movimento, id_lancamento, usuario_atual)
                st.success("Movimento conciliado e lançamento baixado.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))
    finally:
        db.close()


def render_financeiro(usuario_atual):
    render_cabecalho(
        "Financeiro",
        "Controle contas, caixa, lançamentos, relatórios e conciliação bancária.",
    )
    abas = st.tabs(
        [
            "BI Visão Financeira",
            "Fluxo de Caixa",
            "Contas a Receber",
            "Contas a Pagar",
            "Lançamentos Manuais",
            "Relatórios",
            "Conciliação Bancária",
        ]
    )
    with abas[0]:
        _render_bi_visao_financeira()
    with abas[1]:
        _render_fluxo_caixa()
    with abas[2]:
        render_contas_receber(usuario_atual, exibir_cabecalho=False)
    with abas[3]:
        render_contas_pagar(usuario_atual, exibir_cabecalho=False)
    with abas[4]:
        _render_lancamentos_manuais(usuario_atual)
    with abas[5]:
        _render_relatorios()
    with abas[6]:
        _render_conciliacao(usuario_atual)
