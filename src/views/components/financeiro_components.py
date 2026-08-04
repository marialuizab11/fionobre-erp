from datetime import date, datetime

import streamlit as st

from src.database.connection import SessionLocal
from src.services.financeiro_service import (
    STATUS_CANCELADO,
    STATUS_PAGO,
    STATUS_PENDENTE,
    TIPO_PAGAR,
    descricao_lancamento,
    listar_lancamentos,
    registrar_pagamento,
)


def _status_exibicao(lancamento) -> str:
    if (
        lancamento.status_pagamento == STATUS_PENDENTE
        and lancamento.data_vencimento < datetime.now()
    ):
        return "Vencido"
    return lancamento.status_pagamento


def render_lista_contas(tipo_lancamento: str, usuario_atual) -> None:
    """Lista contas a receber ou a pagar e permite registrar sua baixa."""

    chave = "receber" if tipo_lancamento != TIPO_PAGAR else "pagar"
    db = SessionLocal()
    try:
        col_status, col_inicio, col_fim = st.columns(3)
        filtro_status = col_status.selectbox(
            "Status",
            ["Todos", "Pendente", "Pago", "Vencido", "Cancelado"],
            key=f"financeiro_status_{chave}",
        )
        data_inicio = col_inicio.date_input(
            "Vencimento inicial", value=None, key=f"financeiro_inicio_{chave}"
        )
        data_fim = col_fim.date_input(
            "Vencimento final", value=None, key=f"financeiro_fim_{chave}"
        )
        status = None
        vencidas = filtro_status == "Vencido"
        if filtro_status in {STATUS_PENDENTE, STATUS_PAGO, STATUS_CANCELADO}:
            status = filtro_status
        lancamentos = listar_lancamentos(
            db,
            tipo_lancamento=tipo_lancamento,
            status=status,
            apenas_vencidas=vencidas,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        if not lancamentos:
            st.info("Nenhuma conta encontrada para os filtros informados.")
            return

        st.dataframe(
            [
                {
                    "ID": item.id_lancamento,
                    "Origem": item.origem_lancamento.title(),
                    "Descrição": descricao_lancamento(item),
                    "Vencimento": item.data_vencimento.strftime("%d/%m/%Y"),
                    "Pagamento": (
                        item.data_pagamento.strftime("%d/%m/%Y")
                        if item.data_pagamento
                        else "—"
                    ),
                    "Valor (R$)": float(item.valor),
                    "Status": _status_exibicao(item),
                    "Conciliado": "Sim" if item.movimento_extrato else "Não",
                }
                for item in lancamentos
            ],
            use_container_width=True,
            hide_index=True,
        )

        pendentes = [
            item for item in lancamentos if item.status_pagamento == STATUS_PENDENTE
        ]
        if not pendentes:
            return
        mapa = {item.id_lancamento: item for item in pendentes}
        st.markdown("#### Registrar baixa")
        col_conta, col_data, col_botao = st.columns([3, 2, 1])
        id_lancamento = col_conta.selectbox(
            "Conta",
            list(mapa),
            format_func=lambda valor: (
                f"#{valor} — {descricao_lancamento(mapa[valor])} — "
                f"R$ {mapa[valor].valor:.2f}"
            ),
            key=f"financeiro_baixa_conta_{chave}",
        )
        data_baixa = col_data.date_input(
            "Data da baixa", value=date.today(), key=f"financeiro_baixa_data_{chave}"
        )
        texto_botao = "Receber" if chave == "receber" else "Pagar"
        with col_botao:
            st.write("")
            st.write("")
            confirmar = st.button(
                texto_botao,
                type="primary",
                use_container_width=True,
                key=f"financeiro_baixa_botao_{chave}",
            )
        if confirmar:
            try:
                registrar_pagamento(
                    db,
                    id_lancamento,
                    data_pagamento=data_baixa,
                    ator=usuario_atual,
                )
                st.success("Baixa registrada com sucesso.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))
    finally:
        db.close()
