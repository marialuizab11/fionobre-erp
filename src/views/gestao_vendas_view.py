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
        st.markdown(f"## FATURA DE VENDA Nº #{pedido.id_pedido_venda:06d}")
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
        st.markdown(f"**{dt}** — User: {h.nome_usuario or 'SISTEMA'} | Status: `{h.status_anterior or '-'}` -> `{h.status_novo}`")
        if getattr(h, 'justificativa', None):
            st.caption(f"Obs: {h.justificativa}")


@st.dialog("Cancelar Pedido de Venda")
def modal_cancelar_pedido(id_pedido, usuario_atual):
    st.warning(f"Você está prestes a cancelar o pedido/orçamento #{id_pedido}.")
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
                    st.session_state["sucesso_msg"] = f"Orçamento/Pedido #{id_pedido} cancelado com sucesso!"
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao cancelar: {e}")
                finally:
                    db.close()
    with col2:
        if st.button("Voltar", use_container_width=True):
            st.rerun()


def render_gestao_vendas(usuario_atual):
    st.markdown("""
        <style>
            div[data-testid="stModal"] { z-index: 100000 !important; }
            div[data-testid="stPopoverBody"] { z-index: 9999 !important; }
            .block-container { padding-top: 1rem !important; }
            .stTabs { margin-top: -1.5rem !important; }
        </style>
    """, unsafe_allow_html=True)
    
    render_cabecalho("Gestão de Vendas & Orçamentos", "Acompanhe pedidos, emita faturas e gerencie orçamentos e devoluções.")
    
    if "sucesso_msg" in st.session_state:
        st.toast(st.session_state["sucesso_msg"])
        del st.session_state["sucesso_msg"]
    
    db = SessionLocal()
    try:
        aba_pedidos, aba_orcamentos = st.tabs([
            "Pedidos de Venda", 
            "Orçamentos"
        ])

        with aba_pedidos:
            col_status, _ = st.columns([1, 3])
            with col_status:
                filtro_status_ped = st.selectbox("Status do Pedido", options=["Todos", "Confirmado", "Concluído", "Cancelado"], key="filtro_status_ped")
            
            status_param = None if filtro_status_ped == "Todos" else filtro_status_ped
            
            dt_ini_pedidos = datetime.today().date() - timedelta(days=60)
            dt_fim_pedidos = datetime.today().date()
            
            pedidos_brutos_aba = listar_pedidos(db=db, status=status_param, data_inicio=dt_ini_pedidos, data_fim=dt_fim_pedidos)
            pedidos_aba = pedidos_brutos_aba if isinstance(pedidos_brutos_aba, list) else []
            pedidos_vendas = [p for p in pedidos_aba if getattr(p, 'status_venda', '') != "Orcamento"]

            if not pedidos_vendas:
                st.info("Nenhum pedido de venda recente encontrado.")
            else:
                dados_pedidos = []
                for p in pedidos_vendas:
                    dados_pedidos.append({
                        "ID": p.id_pedido_venda,
                        "Data": p.data_venda.strftime('%d/%m/%Y %H:%M') if getattr(p, 'data_venda', None) else "N/A",
                        "Cliente": p.cliente.razao_social if getattr(p, 'cliente', None) else "Desconhecido",
                        "Valor (R$)": f"{float(p.valor_total_pedido or 0):.2f}",
                        "Status": p.status_venda or "Confirmado"
                    })
                
                df_pedidos_tabela = pd.DataFrame(dados_pedidos)
                st.dataframe(df_pedidos_tabela, use_container_width=True, hide_index=True)

                st.markdown("---")
                st.write("#### Ações do Pedido")
                
                col_id, _ = st.columns([2, 4])
                with col_id:
                    pedidos_ids = [p.id_pedido_venda for p in pedidos_vendas]
                    pedido_selecionado_id = st.selectbox("Selecione o ID do pedido para interagir:", options=pedidos_ids, key="sel_ped_acao")
                
                pedido_selecionado_obj = next((p for p in pedidos_vendas if p.id_pedido_venda == pedido_selecionado_id), None)
                
                if pedido_selecionado_obj:
                    b1, b2, b3, b4, b5 = st.columns(5)
                    
                    if b1.button("Fatura / DANFE", key=f"fat_{pedido_selecionado_id}", use_container_width=True):
                        modal_emitir_fatura(pedido_selecionado_id)

                    tem_entrega = getattr(pedido_selecionado_obj, 'entrega', None) is not None
                    entrega_despachada = tem_entrega and pedido_selecionado_obj.entrega.status_logistica in ["Enviado", "Entregue"]
                    disabled_edit = bool(pedido_selecionado_obj.status_venda in ["Cancelado", "Concluído"] or entrega_despachada)
                    
                    if b2.button("Editar", key=f"ed_v_{pedido_selecionado_id}", disabled=disabled_edit, use_container_width=True):
                        modal_editar_pedido(pedido_selecionado_id, usuario_atual)

                    if b3.button("Devolução", key=f"dev_v_{pedido_selecionado_id}", disabled=pedido_selecionado_obj.status_venda == "Cancelado", use_container_width=True):
                        modal_devolucao_venda(pedido_selecionado_id, usuario_atual)

                    if b4.button("Histórico", key=f"hist_{pedido_selecionado_id}", use_container_width=True):
                        modal_historico_pedido(pedido_selecionado_obj)

                    if b5.button("Cancelar", key=f"canc_{pedido_selecionado_id}", disabled=pedido_selecionado_obj.status_venda in ["Cancelado", "Concluído"], use_container_width=True):
                        modal_cancelar_pedido(pedido_selecionado_id, usuario_atual)

        with aba_orcamentos:
            consulta_orc = db.query(PedidoVenda).filter(PedidoVenda.status_venda == "Orcamento").order_by(PedidoVenda.data_venda.desc()).all()
            orcamentos = consulta_orc if isinstance(consulta_orc, list) else []

            if not orcamentos:
                st.info("Nenhum orçamento pendente encontrado.")
            else:
                dados_orcamentos = []
                for orc in orcamentos:
                    dados_orcamentos.append({
                        "ID": orc.id_pedido_venda,
                        "Cliente": orc.cliente.razao_social if getattr(orc, 'cliente', None) else "Desconhecido",
                        "Data": orc.data_venda.strftime('%d/%m/%Y %H:%M') if getattr(orc, 'data_venda', None) else "N/A",
                        "Total (R$)": f"{float(orc.valor_total_pedido or 0):.2f}"
                    })
                
                df_orcamentos = pd.DataFrame(dados_orcamentos)
                st.dataframe(df_orcamentos, use_container_width=True, hide_index=True)

                st.markdown("---")
                st.write("#### Gerenciar Orçamento")
                
                col_id_orc, col_conv, col_canc_orc, _ = st.columns([2, 2, 2, 2])
                with col_id_orc:
                    orc_ids = [o.id_pedido_venda for o in orcamentos]
                    orc_selecionado = st.selectbox("Selecione o ID do Orçamento", options=orc_ids, key="sel_orc_acao")
                
                with col_conv:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Converter em Venda", type="primary", use_container_width=True):
                        try:
                            converter_orcamento_em_venda(db, orc_selecionado, usuario_atual)
                            st.session_state["sucesso_msg"] = f"Orçamento #{orc_selecionado} convertido em venda!"
                            st.rerun()
                        except Exception as e_conv:
                            st.error(f"Erro na conversão: {e_conv}")

                with col_canc_orc:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Cancelar Orçamento", type="secondary", use_container_width=True):
                        modal_cancelar_pedido(orc_selecionado, usuario_atual)

    except Exception as e:
        st.error(f"Erro ao carregar a gestão de vendas: {e}")
        st.exception(e)
    finally:
        db.close()