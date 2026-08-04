import streamlit as st
import pandas as pd
from datetime import datetime
from src.database.connection import SessionLocal
from src.database.models.estoque import LocalizacaoEstoque, InventarioFisico
from src.services.inventario_service import iniciar_inventario, processar_contagem, finalizar_inventario
from src.views.components.ui_components import render_cabecalho

def render_inventario(usuario_atual=1):
    render_cabecalho("Inventario Fisico", "Realize contagens fisicas e ajuste divergencias de estoque.")

    if "sucesso_inv_msg" in st.session_state:
        st.toast(st.session_state["sucesso_inv_msg"], icon="✅")
        del st.session_state["sucesso_inv_msg"]

    db = SessionLocal()
    try:
        inventario_aberto = db.query(InventarioFisico).filter(InventarioFisico.status == "ABERTO").first()
        locais = db.query(LocalizacaoEstoque).filter(LocalizacaoEstoque.ativo == 'S').all()

        if not inventario_aberto:
            st.info("Nenhum inventario fisico em andamento no momento.")
            if not locais:
                st.warning("Cadastre pelo menos uma localizacao de estoque antes de iniciar um inventario.")
            else:
                col_loc, col_obs = st.columns([1, 2])
                with col_loc:
                    local_inv_inic = st.selectbox("Local para Contagem", locais, format_func=lambda x: x.nome, key="loc_inic_inv")
                with col_obs:
                    obs_inv = st.text_input("Observacoes do Inventario", placeholder="Ex: Contagem mensal geral...")

                if st.button("Iniciar Novo Inventario", type="primary"):
                    try:
                        iniciar_inventario(db, local_inv_inic.id_localizacao, usuario_atual, obs_inv)
                        st.session_state["sucesso_inv_msg"] = "Inventario iniciado com sucesso!"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao iniciar inventario: {e}")
        else:
            st.warning(f"Existe um inventario em andamento (ID #{inventario_aberto.id_inventario}) iniciado em {inventario_aberto.data_inicio.strftime('%d/%m/%Y %H:%M')}.")
            st.write(f"**Observacao:** {inventario_aberto.observacoes or 'Nenhuma'}")

            st.markdown("#### Digite a Quantidade Contada para cada Item:")

            with st.form("form_contagem_inventario"):
                payload_contagem = []
                for ii in inventario_aberto.itens:
                    desc_item = ii.item.descricao if ii.item else f"Item #{ii.id_item}"
                    local_nome = ii.localizacao.nome if ii.localizacao else "-"

                    st.markdown(f"**{desc_item}** *(Local: {local_nome} | Saldo Sistema: {float(ii.quantidade_sistema)})*")

                    qtd_contada = st.number_input(
                        f"Quantidade Contada - {desc_item}",
                        min_value=0.0,
                        value=float(ii.quantidade_contada if ii.quantidade_contada is not None else ii.quantidade_sistema),
                        step=1.0,
                        format="%.2f",
                        key=f"cont_{ii.id_item_inventario}"
                    )

                    payload_contagem.append({
                        "id_item_inventario": ii.id_item_inventario,
                        "quantidade_contada": qtd_contada
                    })

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    btn_finalizar = st.form_submit_button("Finalizar Inventario e Ajustar", type="primary", use_container_width=True)
                with col_btn2:
                    btn_cancelar = st.form_submit_button("Cancelar Inventario", use_container_width=True)

                if btn_cancelar:
                    inventario_aberto.status = "CANCELADO"
                    db.commit()
                    st.session_state["sucesso_inv_msg"] = "Inventario cancelado."
                    st.rerun()

                if btn_finalizar:
                    try:
                        processar_contagem(db, payload_contagem)
                        finalizar_inventario(db, inventario_aberto.id_inventario, usuario_atual)

                        st.session_state["sucesso_inv_msg"] = "Inventario finalizado e saldos ajustados com sucesso!"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao finalizar inventario: {e}")

    except Exception as e:
        st.error(f"Erro ao carregar o modulo de inventario: {e}")
    finally:
        db.close()