import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime
from src.database.connection import SessionLocal
from src.services.logistica_service import listar_entregas, atualizar_status_logistica, listar_historico_entrega
from src.views.components.ui_components import render_cabecalho


_USUARIOS_MOCK = [
    {"id_usuario": 1, "nome": "Ana Torres"},
    {"id_usuario": 2, "nome": "Bruno Lima"},
    {"id_usuario": 3, "nome": "Carla Souza"},
]


def _obter_usuario_logado():
    usuario = st.session_state.get("usuario", _USUARIOS_MOCK[0])
    return usuario.get("id_usuario"), usuario.get("nome", "Desconhecido")


def _garantir_usuario_mock():
    """MOCK TEMPORÁRIO — ver docstring de _obter_usuario_logado()."""
    if "usuario" not in st.session_state:
        st.session_state["usuario"] = _USUARIOS_MOCK[0]

    with st.sidebar:
        st.caption("⚠️ Login ainda não implementado — usuário simulado")
        nomes = [u["nome"] for u in _USUARIOS_MOCK]
        atual = st.session_state["usuario"]["nome"]
        escolha = st.selectbox(
            "Simular usuário logado",
            nomes,
            index=nomes.index(atual),
            key="mock_usuario_select"
        )
        st.session_state["usuario"] = next(u for u in _USUARIOS_MOCK if u["nome"] == escolha)


def _mostrar_flash_banner():
    """
    Banner de confirmação que fica visível por alguns segundos (controlado via JS,
    não pelo timer fixo/curto do st.toast) e depois desaparece com fade-out.
    """
    flash = st.session_state.pop("flash_message", None)
    if not flash:
        return

    cor_fundo = "#e6f4ea" if flash["tipo"] == "sucesso" else "#fdecea"
    cor_texto = "#1e7e34" if flash["tipo"] == "sucesso" else "#a71d2a"
    cor_borda = "#b7dfc0" if flash["tipo"] == "sucesso" else "#f3c2c2"

    components.html(f"""
        <div id="flash-banner" style="
            background:{cor_fundo};
            color:{cor_texto};
            border:1px solid {cor_borda};
            padding:12px 16px;
            border-radius:8px;
            font-family: 'Source Sans Pro', sans-serif;
            font-size: 14px;
            margin-bottom: 10px;
            opacity: 1;
            transition: opacity 0.8s ease;
        ">
            {flash["mensagem"]}
        </div>
        <script>
            setTimeout(function() {{
                var el = document.getElementById('flash-banner');
                if (el) {{
                    el.style.opacity = '0';
                }}
            }}, 4500);
        </script>
    """, height=55)

@st.dialog("Histórico de Status")
def _modal_historico(db, id_entrega, id_pedido_str):
    st.markdown(f"**Entrega ID:** {id_entrega} | **Pedido ID:** {id_pedido_str}")
    st.markdown("---")

    historico = listar_historico_entrega(db=db, id_entrega=id_entrega)

    if not historico:
        st.info("Nenhuma alteração de status registrada até agora.")
        return

    for h in historico:
        nome_usuario = h.nome_usuario or "Usuário não identificado"
        data_str = h.data_hora.strftime('%d/%m/%Y às %H:%M:%S')
        status_de = h.status_anterior or "—"
        st.markdown(
            f"**{data_str}** — {nome_usuario}  \n"
            f"`{status_de}` → `{h.status_novo}`"
        )
        st.markdown("---")


def render_logistica():
    render_cabecalho("Gestão Logística", "Painel de controle para acompanhamento de entregas, endereços e despachos.")
    _garantir_usuario_mock()
    _mostrar_flash_banner()
    
    db = SessionLocal()
    try:
        st.subheader("Filtro Operacional")
        opcoes_filtro = ["Todas", "Pendente", "Em separação", "Enviado", "Entregue"]
        filtro_status = st.selectbox(
            "Filtrar por Status",
            options=opcoes_filtro
        )
        
        status_param = None if filtro_status == "Todas" else filtro_status
        entregas = listar_entregas(db=db, status=status_param)
        
        if not entregas:
            st.info("Nenhuma entrega encontrada para o filtro selecionado.")
            return
            
        st.markdown("---")
        st.subheader("Fila de Entregas e Endereços")
        
        for e in entregas:
            pedido = e.pedidos[0] if e.pedidos else None
            cliente = pedido.cliente if pedido else None
            
            id_pedido_str = str(pedido.id_pedido_venda) if pedido else "N/A"
            razao_social = cliente.razao_social if cliente else "N/A"
            
            rua = cliente.rua if cliente and cliente.rua else "N/A"
            numero = cliente.numero if cliente and cliente.numero else "S/N"
            bairro = cliente.bairro if cliente and cliente.bairro else "N/A"
            cidade = cliente.cidade if cliente and cliente.cidade else "N/A"
            uf = cliente.uf if cliente and cliente.uf else "N/A"
            cep = cliente.cep if cliente and cliente.cep else "N/A"
            
            endereco_completo = f"{rua}, {numero} - {bairro}, {cidade} - {uf} (CEP: {cep})"
            status_atual = e.status_logistica
            
            if status_atual == "Expedido":
                status_atual = "Enviado"
            
            with st.container(border=True):
                col_info, col_acao = st.columns([3, 2])

                with col_info:
                    st.markdown(f"**Entrega ID:** {e.id_entrega} | **Pedido ID:** {id_pedido_str}")
                    st.markdown(f"**Cliente:** {razao_social}")
                    st.markdown(f"**Endereço de Entrega:** {endereco_completo}")
                    st.markdown(f"**Status Atual:** {status_atual}")
                    previsao_str = e.data_previsao.strftime('%d/%m/%Y') if e.data_previsao else "N/A"
                    st.markdown(f"**Previsão:** {previsao_str} | **Frete:** R$ {e.valor_frete:.2f}")

                    if st.button("Visualizar histórico", key=f"hist_btn_{e.id_entrega}"):
                        _modal_historico(db=db, id_entrega=e.id_entrega, id_pedido_str=id_pedido_str)

                with col_acao:
                    with st.form(key=f"form_entrega_{e.id_entrega}"):
                        st.markdown("**Atualizar Status:**")

                        opcoes_status = ["Pendente", "Em separação", "Enviado", "Entregue"]
                        indice_atual = opcoes_status.index(status_atual) if status_atual in opcoes_status else 0

                        novo_status_opcao = st.selectbox(
                            "Novo Status",
                            options=opcoes_status,
                            index=indice_atual,
                            key=f"status_select_{e.id_entrega}_{status_atual}"
                        )

                        btn_salvar = st.form_submit_button("Salvar Status", type="primary")

                        if btn_salvar:
                            try:
                                id_usuario_logado, nome_usuario_logado = _obter_usuario_logado()
                                atualizar_status_logistica(
                                    db=db,
                                    id_entrega=e.id_entrega,
                                    novo_status=novo_status_opcao,
                                    id_usuario=id_usuario_logado,
                                    nome_usuario=nome_usuario_logado,
                                )
                                st.session_state["flash_message"] = {
                                    "tipo": "sucesso",
                                    "mensagem": f"Status atualizado para **{novo_status_opcao}** por {nome_usuario_logado}.",
                                }
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Erro ao atualizar: {ex}")
                                
    except Exception as e:
        st.error(f"Erro na tela de logística: {e}")
    finally:
        db.close()