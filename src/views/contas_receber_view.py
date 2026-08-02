import streamlit as st
from datetime import datetime
from src.database.connection import SessionLocal
from src.services.financeiro_service import listar_lancamentos, registrar_pagamento
from src.views.components.ui_components import render_cabecalho

@st.dialog("Registrar Pagamento")
def modal_registrar_pagamento(id_lancamento, valor):
    st.warning(f"Confirma o recebimento do lançamento #{id_lancamento} no valor de R$ {valor:.2f}?")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Confirmar", type="primary", use_container_width=True):
            db = SessionLocal()
            try:
                registrar_pagamento(db=db, id_lancamento=id_lancamento)
                st.toast("Pagamento baixado com sucesso!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao baixar pagamento: {e}")
            finally:
                db.close()
                
    with col2:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()

def render_contas_receber():
    render_cabecalho("Contas a Receber", "Gerencie os recebimentos e acompanhe lançamentos pendentes ou vencidos.")
    
    db = SessionLocal()
    try:
        st.subheader("Filtros")
        
        filtro_status = st.selectbox(
            "Status do Pagamento",
            options=["Todos", "Pendente", "Pago", "Vencido"]
        )
        
        status_param = None
        apenas_vencidas = False
        
        if filtro_status in ["Pendente", "Pago"]:
            status_param = filtro_status
        elif filtro_status == "Vencido":
            apenas_vencidas = True
            
        lancamentos = listar_lancamentos(
            db=db, 
            tipo_lancamento="CONTA_A_RECEBER", 
            status=status_param, 
            apenas_vencidas=apenas_vencidas
        )
        
        if not lancamentos:
            st.info("Nenhum lançamento financeiro encontrado com os filtros atuais.")
            return
            
        st.markdown("---")
        
        c_head = st.columns([1, 1.5, 3, 2, 2, 2, 1.5])
        c_head[0].write("**ID**")
        c_head[1].write("**Pedido**")
        c_head[2].write("**Cliente**")
        c_head[3].write("**Vencimento**")
        c_head[4].write("**Valor (R$)**")
        c_head[5].write("**Status**")
        c_head[6].write("**Ação**")
        st.markdown("---") 
        
        for lanc in lancamentos:
            c_row = st.columns([1, 1.5, 3, 2, 2, 2, 1.5])
            
            c_row[0].write(str(lanc.id_lancamento))
            
            if lanc.pedido_venda:
                c_row[1].write(f"#{lanc.id_pedido_venda}")
                cliente_nome = lanc.pedido_venda.cliente.razao_social if lanc.pedido_venda.cliente else "Desconhecido"
                c_row[2].write(cliente_nome)
            else:
                c_row[1].write("N/A")
                c_row[2].write("Avulso")
                
            vencimento_str = lanc.data_vencimento.strftime('%d/%m/%Y') if lanc.data_vencimento else "N/A"
            c_row[3].write(vencimento_str)
            
            c_row[4].write(f"{lanc.valor:.2f}")
            
            hoje = datetime.now()
            if lanc.status_pagamento == "Cancelado":
                c_row[5].write("Cancelado")
            elif lanc.status_pagamento == "Pago":
                c_row[5].write("Pago")
            elif lanc.status_pagamento == "Pendente" and lanc.data_vencimento < hoje:
                c_row[5].write("Vencido")
            else:
                c_row[5].write("Pendente")
            
            with c_row[6]:
                disabled = lanc.status_pagamento in ["Pago", "Cancelado"]
                if st.button("Dar Baixa", key=f"baixa_{lanc.id_lancamento}", disabled=disabled, use_container_width=True):
                    modal_registrar_pagamento(id_lancamento=lanc.id_lancamento, valor=lanc.valor)
                    
    except Exception as e:
        st.error(f"Erro ao carregar contas a receber: {e}")
    finally:
        db.close()