import traceback
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from src.database.connection import SessionLocal
from src.database.models.vendas import PedidoVenda
from src.database.models.cadastros import Item
from src.services.venda_service import (
    listar_pedidos,
    cancelar_venda,
    editar_pedido_venda,
    registrar_devolucao_venda,
    converter_orcamento_em_venda,
)
from src.services.logistica_service import listar_historico_entrega
from src.views.components.ui_components import render_cabecalho


@st.dialog("Emissão de Fatura / Comprovante de Venda", width="large")
def modal_emitir_fatura(pedido_id):
    db = SessionLocal()
    try:
        pedido = db.query(PedidoVenda).get(pedido_id)
        if not pedido:
            st.error("Pedido não encontrado.")
            return

        cliente = pedido.cliente
        st.markdown(f"## 📄 FATURA DE VENDA Nº #{pedido.id_pedido_venda:06d}")
        st.caption(f"Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        st.divider()

        col_cli, col_emp = st.columns(2)
        with col_cli:
            st.markdown("**DESTINATÁRIO / CLIENTE**")
            st.write(f"**Razão Social:** {cliente.razao_social if cliente else 'N/A'}")
            st.write(f"**CPF/CNPJ:** {cliente.cnpj_cpf if cliente else 'N/A'}")
            st.write(f"**E-mail:** {cliente.email if cliente else 'N/A'}")
            st.write(f"**Cidade/UF:** {cliente.cidade or '-'}/{cliente.uf or '-'}")

        with col_emp:
            st.markdown("**EMISSOR**")
            st.write("**FioNobre ERP S.A.**")
            st.write("**CNPJ:** 00.000.000/0001-99")
            st.write(f"**Status da Venda:** {pedido.status_venda or 'N/A'}")

        st.divider()
        st.markdown("### Itens Faturados")
        
        dados_itens = []
        for iv in (pedido.itens or []):
            qtd = float(iv.quantidade_vendida or 0)
            vlr = float(iv.valor_unitario or 0)
            desc = iv.item.descricao if iv.item else f"#{iv.id_item}"
            dados_itens.append({
                "Item": desc,
                "Qtd": qtd,
                "Valor Unit. (R$)": f"{vlr:.2f}",
                "Total (R$)": f"{(qtd * vlr):.2f}",
            })
        st.dataframe(pd.DataFrame(dados_itens), use_container_width=True, hide_index=True)

        val_tot = float(pedido.valor_total_pedido or 0)
        st.markdown(f"### **Valor Total da Fatura: R$ {val_tot:.2f}**")
        st.info("Documento gerado para fins de simples faturamento e conferência do cliente.")
    finally:
        db.close()


@st.dialog("Editar Pedido de Venda", width="large")
def modal_editar_pedido(pedido_id, usuario_atual):
    db = SessionLocal()
    try:
        pedido = db.query(PedidoVenda).get(pedido_id)
        if not pedido:
            st.error("Pedido não encontrado.")
            return

        itens_disponiveis = db.query(Item).filter(Item.tipo_item == "PRODUTO_ACABADO").all() or []
        item_map = {i.id_item: i for i in itens_disponiveis}

        st.write(f"Editando os itens do **Pedido #{pedido_id}**")

        itens_atuais_ids = [iv.id_item for iv in (pedido.itens or []) if iv.id_item in item_map]
        selecionados = st.multiselect(
            "Selecione os Produtos",
            list(item_map.keys()),
            default=itens_atuais_ids,
            format_func=lambda x: f"{item_map[x].descricao} (Preço: R$ {float(item_map[x].preco_venda or 0):.2f})"
        )

        qtds_e_precos = {iv.id_item: (float(iv.quantidade_vendida or 0), float(iv.valor_unitario or 0)) for iv in (pedido.itens or [])}

        with st.form("form_ed_venda"):
            novos_itens_payload = []
            for id_i in selecionados:
                item_obj = item_map[id_i]
                q_def, p_def = qtds_e_precos.get(id_i, (1.0, float(item_obj.preco_venda or 0)))
                
                col1, col2 = st.columns(2)
                st.markdown(f"**{item_obj.descricao}**")
                q = col1.number_input(f"Qtd", min_value=0.01, value=max(q_def, 0.01), key=f"q_{id_i}")
                p = col2.number_input(f"Preço (R$)", min_value=0.0, value=max(p_def, 0.0), key=f"p_{id_i}")
                novos_itens_payload.append({"id_item": id_i, "quantidade": q, "valor_unitario": p})

            if st.form_submit_button("Salvar Alterações", type="primary", use_container_width=True):
                try:
                    editar_pedido_venda(db, pedido_id, novos_itens_payload, usuario_atual)
                    st.session_state["sucesso_msg"] = "Pedido atualizado com sucesso!"
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao editar: {e}")
    finally:
        db.close()


@st.dialog("Registrar Devolução / Estorno", width="large")
def modal_devolucao_venda(pedido_id, usuario_atual):
    db = SessionLocal()
    try:
        pedido = db.query(PedidoVenda).get(pedido_id)
        if not pedido:
            st.error("Pedido não encontrado.")
            return

        st.write(f"Informe os itens e quantidades a serem devolvidos do **Pedido #{pedido_id}**:")
        st.caption("A devolução estornará a quantidade para o estoque e ajustará o financeiro do cliente.")

        with st.form("form_devolucao"):
            itens_devolucao_payload = []
            for iv in (pedido.itens or []):
                q_max = float(iv.quantidade_vendida or 0)
                desc = iv.item.descricao if iv.item else f"Item #{iv.id_item}"
                st.markdown(f"**{desc}** (Comprado: {q_max})")
                q_dev = st.number_input(
                    "Qtd a Devolver",
                    min_value=0.0,
                    max_value=max(q_max, 0.0),
                    value=0.0,
                    key=f"dev_{iv.id_item}"
                )
                if q_dev > 0:
                    itens_devolucao_payload.append({"id_item": iv.id_item, "quantidade_devolver": q_dev})

            motivo = st.text_area("Motivo da Devolução *", placeholder="Descreva o motivo (mínimo 5 caracteres)...")

            if st.form_submit_button("Processar Devolução", type="primary", use_container_width=True):
                if not itens_devolucao_payload:
                    st.error("Informe pelo menos um item com quantidade maior que zero para devolver.")
                else:
                    try:
                        registrar_devolucao_venda(db, pedido_id, itens_devolucao_payload, motivo, usuario_atual)
                        st.session_state["sucesso_msg"] = "Devolução processada com sucesso!"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro na devolução: {e}")
    finally:
        db.close()


@st.dialog("Histórico de Ações do Pedido")
def modal_historico_pedido(pedido_obj):
    st.write(f"**Trilha de auditoria do pedido #{pedido_obj.id_pedido_venda}**")
    st.divider()
    historico = getattr(pedido_obj, 'historico_status', None)
    if not historico:
        st.info("Nenhum histórico registrado para este pedido.")
        return

    for h in historico:
        dt = h.data_hora.strftime('%d/%m/%Y às %H:%M:%S') if getattr(h, 'data_hora', None) else "N/A"
        st.markdown(f"⏱️ **{dt}** — User: {h.nome_usuario or 'SISTEMA'} | Status: `{h.status_anterior or '-'}` ➡️ `{h.status_novo}`")
        if getattr(h, 'justificativa', None):
            st.caption(f"Obs: {h.justificativa}")


@st.dialog("Cancelar Pedido de Venda")
def modal_cancelar_pedido(id_pedido, usuario_atual):
    st.warning(f"Você está prestes a cancelar o pedido #{id_pedido}.")
    justificativa = st.text_area("Justificativa do Cancelamento", placeholder="Informe o motivo (mínimo de 5 caracteres)...")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirmar Cancelamento", type="primary", use_container_width=True):
            if len(justificativa.strip()) < 5:
                st.error("A justificativa deve ter pelo menos 5 caracteres.")
            else:
                db = SessionLocal()
                try:
                    cancelar_venda(db=db, id_pedido=id_pedido, justificativa=justificativa, usuario=usuario_atual)
                    st.session_state["sucesso_msg"] = f"Pedido #{id_pedido} cancelado com sucesso!"
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao cancelar: {e}")
                finally:
                    db.close()
    with col2:
        if st.button("Voltar", use_container_width=True):
            st.rerun()


def render_gestao_vendas(usuario_atual):
    render_cabecalho("Gestão de Vendas & Orçamentos", "Acompanhe pedidos, emita faturas e gerencie orçamentos e devoluções.")
    
    if "sucesso_msg" in st.session_state:
        st.toast(st.session_state["sucesso_msg"], icon="✅")
        del st.session_state["sucesso_msg"]

    st.markdown("""
        <style>
            div[data-testid="stModal"] {
                z-index: 100000 !important;
            }
            div[data-testid="stPopoverBody"] {
                z-index: 9999 !important;
            }
        </style>
    """, unsafe_allow_html=True)
    
    db = SessionLocal()
    try:
        aba_pedidos, aba_orcamentos = st.tabs(["Pedidos de Venda", "Orçamentos"])

        with aba_pedidos:
            col_status, col_dt_ini, col_dt_fim = st.columns(3)
            with col_status:
                filtro_status = st.selectbox("Status do Pedido", options=["Todos", "Confirmado", "Concluído", "Cancelado"])
            
            with col_dt_ini:
                data_inicio_raw = st.date_input("Data Inicial", value=datetime.today().date() - timedelta(days=30))
                data_inicio = data_inicio_raw[0] if isinstance(data_inicio_raw, tuple) and data_inicio_raw else data_inicio_raw
                if not data_inicio:
                    data_inicio = datetime.today().date()
            
            with col_dt_fim:
                data_fim_raw = st.date_input("Data Final", value=datetime.today().date())
                data_fim = data_fim_raw[0] if isinstance(data_fim_raw, tuple) and data_fim_raw else data_fim_raw
                if not data_fim:
                    data_fim = datetime.today().date()

            status_param = None if filtro_status == "Todos" else filtro_status
            
            pedidos_brutos = listar_pedidos(db=db, status=status_param, data_inicio=data_inicio, data_fim=data_fim)
            pedidos = pedidos_brutos if isinstance(pedidos_brutos, list) else []
            pedidos_vendas = [p for p in pedidos if getattr(p, 'status_venda', '') != "Orcamento"]

            if not pedidos_vendas:
                st.info("Nenhum pedido de venda encontrado com os filtros atuais.")
            else:
                st.markdown("---")
                c_head = st.columns([1, 2, 3, 2, 2, 2])
                c_head[0].write("**ID**")
                c_head[1].write("**Data**")
                c_head[2].write("**Cliente**")
                c_head[3].write("**Valor (R$)**")
                c_head[4].write("**Status**")
                c_head[5].write("**Ações**")
                st.markdown("---")

                for p in pedidos_vendas:
                    val_p = float(p.valor_total_pedido or 0)
                    c_row = st.columns([1, 2, 3, 2, 2, 2])
                    c_row[0].write(str(p.id_pedido_venda))
                    c_row[1].write(p.data_venda.strftime('%d/%m/%Y %H:%M') if getattr(p, 'data_venda', None) else "N/A")
                    c_row[2].write(p.cliente.razao_social if getattr(p, 'cliente', None) else "Desconhecido")
                    c_row[3].write(f"{val_p:.2f}")
                    c_row[4].write(p.status_venda or "Confirmado")

                    with c_row[5]:
                        with st.popover("⋮", use_container_width=True):
                            if st.button("Fatura/DANFE", key=f"fat_{p.id_pedido_venda}", use_container_width=True):
                                modal_emitir_fatura(p.id_pedido_venda)

                            tem_entrega = getattr(p, 'entrega', None) is not None
                            entrega_despachada = tem_entrega and p.entrega.status_logistica in ["Enviado", "Entregue"]
                            disabled_edit = bool(p.status_venda in ["Cancelado", "Concluído"] or entrega_despachada)
                            
                            if st.button("Editar", key=f"ed_v_{p.id_pedido_venda}", disabled=disabled_edit, use_container_width=True):
                                modal_editar_pedido(p.id_pedido_venda, usuario_atual)

                            if st.button("Devolução", key=f"dev_v_{p.id_pedido_venda}", disabled=p.status_venda == "Cancelado", use_container_width=True):
                                modal_devolucao_venda(p.id_pedido_venda, usuario_atual)

                            if st.button("Histórico", key=f"hist_{p.id_pedido_venda}", use_container_width=True):
                                modal_historico_pedido(p)

                            if st.button("Cancelar", key=f"canc_{p.id_pedido_venda}", disabled=p.status_venda in ["Cancelado", "Concluído"], use_container_width=True):
                                modal_cancelar_pedido(p.id_pedido_venda, usuario_atual)

        with aba_orcamentos:
            consulta_orc = db.query(PedidoVenda).filter(PedidoVenda.status_venda == "Orcamento").order_by(PedidoVenda.data_venda.desc()).all()
            orcamentos = consulta_orc if isinstance(consulta_orc, list) else []

            if not orcamentos:
                st.info("Nenhum orçamento pendente encontrado.")
            else:
                c_h = st.columns([1, 2, 3, 2, 2])
                c_h[0].write("**ID**")
                c_h[1].write("**Data**")
                c_h[2].write("**Cliente**")
                c_h[3].write("**Total (R$)**")
                c_h[4].write("**Ação**")
                st.markdown("---")

                for orc in orcamentos:
                    val_o = float(orc.valor_total_pedido or 0)
                    c_r = st.columns([1, 2, 3, 2, 2])
                    c_r[0].write(str(orc.id_pedido_venda))
                    c_r[1].write(orc.data_venda.strftime('%d/%m/%Y %H:%M') if getattr(orc, 'data_venda', None) else "N/A")
                    c_r[2].write(orc.cliente.razao_social if getattr(orc, 'cliente', None) else "-")
                    c_r[3].write(f"{val_o:.2f}")

                    with c_r[4]:
                        if st.button("Converter em Venda", key=f"conv_{orc.id_pedido_venda}", type="primary", use_container_width=True):
                            try:
                                converter_orcamento_em_venda(db, orc.id_pedido_venda, usuario_atual)
                                st.session_state["sucesso_msg"] = f"Orçamento #{orc.id_pedido_venda} convertido em venda!"
                                st.rerun()
                            except Exception as e_conv:
                                st.error(f"Erro na conversão: {e_conv}")

    except Exception as e:
        st.error(f"Erro ao carregar a gestão de vendas: {e}")
        st.exception(e)
    finally:
        db.close()