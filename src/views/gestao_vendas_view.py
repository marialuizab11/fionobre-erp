import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from src.database.connection import SessionLocal
from src.database.models.vendas import PedidoVenda
from src.services.venda_service import listar_pedidos, cancelar_venda
from src.services.logistica_service import listar_historico_entrega
from src.views.components.ui_components import render_cabecalho

@st.dialog("Histórico de Ações do Pedido")
def modal_historico_pedido(pedido_obj):
    st.write(f"**Trilha de auditoria do pedido #ID {pedido_obj.id_pedido_venda}**")
    st.divider()
    
    data_criacao = pedido_obj.data_venda.strftime('%d/%m/%Y às %H:%M:%S') if pedido_obj.data_venda else "Desconhecida"
    st.markdown(f"**{data_criacao}** — Pedido criado no sistema. (Status: Confirmado)")
    
    if pedido_obj.id_entrega:
        db = SessionLocal()
        try:
            historico_logistica = listar_historico_entrega(db=db, id_entrega=pedido_obj.id_entrega)
            for h in reversed(historico_logistica):
                data_str = h.data_hora.strftime('%d/%m/%Y às %H:%M:%S')
                st.markdown(f"📦 **{data_str}** — Logística: {h.status_anterior} ➡️ {h.status_novo}")
        except Exception as e:
            st.error(f"Não foi possível carregar o log de logística: {e}")
        finally:
            db.close()

    if pedido_obj.status_venda == "Cancelado":
        st.markdown(f"**Cancelado** — Motivo: {pedido_obj.justificativa_cancelamento}")
    
    if pedido_obj.status_venda == "Concluído":
        st.markdown(f"✅ **Concluído** — O fluxo deste pedido foi finalizado com sucesso.")

@st.dialog("Cancelar Pedido de Venda")
def modal_cancelar_pedido(id_pedido):
    st.warning(f"Você está prestes a cancelar o pedido #ID {id_pedido}.")
    st.write("Esta ação estornará o estoque, inativará o lançamento financeiro e suspenderá a entrega logística se a mercadoria ainda não tiver sido enviada.")
    
    justificativa = st.text_area("Justificativa do Cancelamento", placeholder="Informe o motivo (mínimo de 5 caracteres)...")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirmar Cancelamento", type="primary", use_container_width=True):
            if len(justificativa.strip()) < 5:
                st.error("A justificativa deve ter pelo menos 5 caracteres.")
            else:
                db = SessionLocal()
                try:
                    cancelar_venda(db=db, id_pedido=id_pedido, justificativa=justificativa, id_usuario=1)
                    st.toast(f"Pedido #{id_pedido} cancelado com sucesso!", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao cancelar: {e}")
                finally:
                    db.close()
                    
    with col2:
        if st.button("Voltar", use_container_width=True):
            st.rerun()

@st.dialog("Detalhes do Pedido", width="large")
def modal_detalhes_pedido(id_pedido):
    db = SessionLocal()
    try:
        # Busca o pedido fresco do banco para carregar os relacionamentos sem erro de sessão
        pedido = db.query(PedidoVenda).filter(PedidoVenda.id_pedido_venda == id_pedido).first()
        
        if not pedido:
            st.error("Pedido não encontrado.")
            return

        col_cli, col_status = st.columns(2)
        
        with col_cli:
            st.markdown("### 🛒 Informações Gerais")
            cliente_nome = pedido.cliente.razao_social if pedido.cliente else "Desconhecido"
            st.write(f"**Cliente:** {cliente_nome}")
            st.write(f"**Data da Venda:** {pedido.data_venda.strftime('%d/%m/%Y %H:%M')}")
            st.write(f"**Valor Total:** R$ {pedido.valor_total_pedido:.2f}")

        with col_status:
            st.markdown("### 🚦 Status Cruzado")
            st.write(f"**Operacional (Venda):** {pedido.status_venda}")
            
            # Busca status Logístico
            if pedido.entrega:
                st.write(f"**Logística:** {pedido.entrega.status_logistica}")
            else:
                st.write("**Logística:** Retirada na Loja / Sem entrega")
                
            # Busca status Financeiro
            if pedido.lancamentos:
                status_fin = pedido.lancamentos[0].status_pagamento
                st.write(f"**Financeiro:** {status_fin}")
            else:
                st.write("**Financeiro:** Sem lançamento")

        st.divider()
        st.markdown("### 📦 Itens Comprados")
        
        dados_itens = []
        for iv in pedido.itens:
            desc = iv.item.descricao if iv.item else f"Item ID {iv.id_item}"
            subtotal = float(iv.quantidade_vendida * iv.valor_unitario)
            dados_itens.append({
                "Produto": desc,
                "Qtd": float(iv.quantidade_vendida),
                "Vlr. Unitário (R$)": f"{float(iv.valor_unitario):.2f}",
                "Subtotal (R$)": f"{subtotal:.2f}"
            })

        if dados_itens:
            df_itens = pd.DataFrame(dados_itens)
            st.dataframe(df_itens, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum item vinculado a este pedido.")

    except Exception as e:
        st.error(f"Erro ao carregar os detalhes: {e}")
    finally:
        db.close()

def render_gestao_vendas():
    render_cabecalho("Gestão de Vendas", "Acompanhe o histórico de pedidos e gerencie ações operacionais.")
    
    db = SessionLocal()
    try:
        st.subheader("Filtros")
        
        col_status, col_dt_ini, col_dt_fim = st.columns(3)
        with col_status:
            filtro_status = st.selectbox(
                "Status do Pedido",
                options=["Todos", "Confirmado", "Concluído", "Cancelado"]
            )
        with col_dt_ini:
            data_inicio = st.date_input("Data Inicial", value=datetime.now() - timedelta(days=30))
        with col_dt_fim:
            data_fim = st.date_input("Data Final", value=datetime.now())
            
        if data_inicio > data_fim:
            st.error("A data inicial não pode ser maior que a data final.")
            return
        
        status_param = None if filtro_status == "Todos" else filtro_status
        pedidos = listar_pedidos(db=db, status=status_param, data_inicio=data_inicio, data_fim=data_fim)
        
        if not pedidos:
            st.info("Nenhum pedido encontrado com os filtros atuais.")
            return
            
        st.markdown("---")
        
        # Cabeçalho da Tabela Compacto
        c_head = st.columns([1, 2, 3, 2, 2, 1])
        c_head[0].write("**ID**")
        c_head[1].write("**Data**")
        c_head[2].write("**Cliente**")
        c_head[3].write("**Valor (R$)**")
        c_head[4].write("**Status**")
        c_head[5].write("**Ações**")
        st.markdown("---") # Apenas um divisor para separar o cabeçalho
        
        # Corpo da Tabela (Sem borders, sem dividers intermediários)
        for p in pedidos:
            cliente_nome = p.cliente.razao_social if p.cliente else "Desconhecido"
            data_str = p.data_venda.strftime('%d/%m/%Y %H:%M') if p.data_venda else "N/A"
            
            c_row = st.columns([1, 2, 3, 2, 2, 1])
            c_row[0].write(str(p.id_pedido_venda))
            c_row[1].write(data_str)
            c_row[2].write(cliente_nome)
            c_row[3].write(f"{p.valor_total_pedido:.2f}")
            
            if p.status_venda == "Cancelado":
                c_row[4].write("Cancelado")
            elif p.status_venda == "Concluído":
                c_row[4].write("Concluído")
            else:
                c_row[4].write("Confirmado")
            
            with c_row[5]:
                with st.popover("⋮", use_container_width=True):
                    if st.button("Ver Detalhes", key=f"det_{p.id_pedido_venda}", use_container_width=True):
                        modal_detalhes_pedido(id_pedido=p.id_pedido_venda)
                    
                    if st.button("Ver Histórico", key=f"hist_{p.id_pedido_venda}", use_container_width=True):
                        modal_historico_pedido(pedido_obj=p)
                        
                    disabled = p.status_venda in ["Cancelado", "Concluído"]
                    if st.button("Cancelar Pedido", key=f"canc_{p.id_pedido_venda}", disabled=disabled, use_container_width=True):
                        modal_cancelar_pedido(id_pedido=p.id_pedido_venda)

    except Exception as e:
        st.error(f"Erro ao carregar a gestão de vendas: {e}")
    finally:
        db.close()