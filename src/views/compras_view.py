from datetime import date, timedelta
import streamlit as st

from src.database.connection import SessionLocal
from src.database.models.cadastros import Item
from src.database.models.compras import Fornecedor, NecessidadeCompra
from src.services.compra_service import (
    cancelar_compra,
    confirmar_compra,
    criar_pedido_por_necessidades,
    criar_pedido_compra,
    editar_pedido_compra,
    remover_pedido_compra,
    listar_pedidos_compra,
    receber_compra,
)
from src.views.components.ui_components import render_cabecalho


# ==========================================
# MODAIS DE EDIÇÃO E REMOÇÃO DE PEDIDO
# ==========================================

@st.dialog("Editar Pedido de Compra")
def modal_editar_pedido(pedido, usuario_atual):
    db = SessionLocal()
    try:
        fornecedores = db.query(Fornecedor).order_by(Fornecedor.razao_social).all()
        itens = db.query(Item).order_by(Item.descricao).all()
        
        fornecedor_map = {f.id_fornecedor: f for f in fornecedores}
        item_map = {i.id_item: i for i in itens}

        # Fornecedor Atual
        idx_forn = list(fornecedor_map.keys()).index(pedido.id_fornecedor) if pedido.id_fornecedor in fornecedor_map else 0
        fornecedor_id = st.selectbox(
            "Fornecedor",
            list(fornecedor_map.keys()),
            index=idx_forn,
            format_func=lambda valor: fornecedor_map[valor].razao_social,
        )

        # Itens Atuais
        itens_selecionados_ids = [linha.id_item for linha in pedido.itens if linha.id_item in item_map]
        itens_ids = st.multiselect(
            "Itens da compra",
            list(item_map.keys()),
            default=itens_selecionados_ids,
            format_func=lambda valor: f"{item_map[valor].descricao} — Saldo: {item_map[valor].saldo_estoque}",
        )

        quantidades_e_custos = {linha.id_item: (float(linha.quantidade_comprada), float(linha.custo_unitario)) for linha in pedido.itens}

        with st.form("form_editar_pedido"):
            linhas = []
            for item_id in itens_ids:
                item = item_map[item_id]
                st.markdown(f"**{item.descricao}**")
                
                qtd_padrao, custo_padrao = quantidades_e_custos.get(item_id, (1.0, float(item.custo_medio or 0)))
                
                col1, col2 = st.columns(2)
                quantidade = col1.number_input("Quantidade", min_value=0.01, value=qtd_padrao, key=f"ed_qtd_{item_id}")
                custo = col2.number_input("Custo unitário (R$)", min_value=0.0, value=custo_padrao, key=f"ed_custo_{item_id}")
                linhas.append({"id_item": item_id, "quantidade": quantidade, "custo_unitario": custo})
                
            if st.form_submit_button("Salvar Alterações", type="primary", use_container_width=True):
                try:
                    editar_pedido_compra(db, pedido.id_pedido_compra, fornecedor_id, linhas, usuario_atual.id_usuario)
                    st.toast("Pedido atualizado com sucesso!", icon="✅")
                    st.rerun()
                except Exception as erro:
                    st.error(str(erro))
    finally:
        db.close()


@st.dialog("Remover Pedido de Compra")
def modal_remover_pedido(pedido, usuario_atual):
    st.warning(f"Tem certeza que deseja excluir permanentemente o Pedido de Compra **#{pedido.id_pedido_compra}**?")
    st.caption("Esta ação liberará eventuais necessidades do PCP vinculadas e não poderá ser desfeita.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirmar Exclusão", type="primary", use_container_width=True):
            db = SessionLocal()
            try:
                remover_pedido_compra(db, pedido.id_pedido_compra, usuario_atual.id_usuario)
                st.toast("Pedido removido com sucesso!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(str(e))
            finally:
                db.close()
    with col2:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()


def _novo_pedido(db, usuario_atual):
    # Exibe o toast e limpa o flag da sessão
    if "toast_pedido_criado" in st.session_state:
        msg = st.session_state.pop("toast_pedido_criado")
        st.toast(msg, icon="✅")

    fornecedores = db.query(Fornecedor).order_by(Fornecedor.razao_social).all()
    itens = db.query(Item).order_by(Item.descricao).all()
    if not fornecedores or not itens:
        st.info("Cadastre pelo menos um fornecedor no Módulo de Cadastros e um item antes de criar uma compra.")
        return

    fornecedor_map = {f.id_fornecedor: f for f in fornecedores}
    item_map = {i.id_item: i for i in itens}
    
    # Controle de versão do formulário para reset limpo
    if "form_compra_versao" not in st.session_state:
        st.session_state["form_compra_versao"] = 0

    versao = st.session_state["form_compra_versao"]

    fornecedor_id = st.selectbox(
        "Fornecedor",
        list(fornecedor_map),
        key=f"compra_fornecedor_{versao}",
        format_func=lambda valor: fornecedor_map[valor].razao_social,
    )
    itens_ids = st.multiselect(
        "Itens da compra",
        list(item_map),
        key=f"compra_itens_{versao}",
        format_func=lambda valor: (
            f"{item_map[valor].descricao} — saldo {item_map[valor].saldo_estoque} "
            f"{item_map[valor].unidade_medida}"
        ),
    )

    with st.form("novo_pedido_compra", clear_on_submit=True):
        linhas = []
        for item_id in itens_ids:
            item = item_map[item_id]
            st.markdown(f"**{item.descricao}**")
            col1, col2 = st.columns(2)
            quantidade = col1.number_input(
                "Quantidade", min_value=0.01, value=1.0, key=f"compra_qtd_{item_id}_{versao}"
            )
            custo = col2.number_input(
                "Custo unitário (R$)", min_value=0.0,
                value=float(item.custo_medio or 0), key=f"compra_custo_{item_id}_{versao}",
            )
            linhas.append({"id_item": item_id, "quantidade": quantidade, "custo_unitario": custo})
            
        criar = st.form_submit_button("Criar pedido de compra", type="primary", use_container_width=True)

    if criar:
        try:
            pedido = criar_pedido_compra(db, fornecedor_id, linhas, usuario_atual.id_usuario)
            
            # Incrementa a versão do formulário para forçar a criação de widgets limpos no rerun
            st.session_state["form_compra_versao"] += 1
            
            # Define a mensagem do Toast
            st.session_state["toast_pedido_criado"] = f"Pedido de compra #{pedido.id_pedido_compra} criado com sucesso!"
            st.rerun()
        except Exception as erro:
            st.error(str(erro))
                        
def _gerenciar_pedidos(db, usuario_atual):
    pedidos = listar_pedidos_compra(db)
    if not pedidos:
        st.info("Nenhum pedido de compra cadastrado.")
        return

    pedido_map = {p.id_pedido_compra: p for p in pedidos}
    pedido_id = st.selectbox(
        "Selecione o Pedido",
        list(pedido_map),
        format_func=lambda valor: (
            f"#{valor} — {pedido_map[valor].fornecedor.razao_social} — "
            f"{pedido_map[valor].status_compra} — R$ {pedido_map[valor].valor_total_pedido:.2f}"
        ),
    )
    pedido = pedido_map[pedido_id]

    col_info1, col_info2 = st.columns([3, 1])
    with col_info1:
        st.subheader(f"Pedido #{pedido.id_pedido_compra} ({pedido.status_compra})")
    with col_info2:
        if pedido.status_compra == "Criado":
            col_b1, col_b2 = st.columns(2)
            if col_b1.button("✏️ Editar", use_container_width=True):
                modal_editar_pedido(pedido, usuario_atual)
            if col_b2.button("🗑️ Excluir", use_container_width=True):
                modal_remover_pedido(pedido, usuario_atual)

    st.dataframe(
        [{
            "Item": linha.item.descricao,
            "Quantidade": float(linha.quantidade_comprada),
            "Custo unitário (R$)": float(linha.custo_unitario),
            "Subtotal (R$)": float(linha.quantidade_comprada * linha.custo_unitario),
        } for linha in pedido.itens],
        use_container_width=True,
        hide_index=True,
    )

    if pedido.status_compra == "Criado":
        if st.button("Confirmar pedido", type="primary", use_container_width=True):
            try:
                confirmar_compra(db, pedido_id, usuario_atual.id_usuario)
                st.success("Pedido confirmado.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))
    elif pedido.status_compra == "Confirmado":
        vencimento = st.date_input(
            "Vencimento da conta a pagar", value=date.today() + timedelta(days=30)
        )
        if st.button("Registrar recebimento", type="primary", use_container_width=True):
            try:
                receber_compra(db, pedido_id, vencimento, usuario_atual.id_usuario)
                st.success("Compra recebida; estoque e financeiro atualizados.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))

    if pedido.status_compra not in ["Cancelado", "Recebido"]:
        with st.expander("Cancelar Pedido"):
            with st.form(f"cancelar_compra_{pedido_id}"):
                justificativa = st.text_area("Justificativa para cancelamento")
                cancelar = st.form_submit_button("Confirmar Cancelamento")
            if cancelar:
                try:
                    cancelar_compra(db, pedido_id, justificativa, usuario_atual.id_usuario)
                    st.success("Pedido cancelado.")
                    st.rerun()
                except Exception as erro:
                    st.error(str(erro))


def _necessidades_compra(db, usuario_atual):
    necessidades = db.query(NecessidadeCompra).order_by(
        NecessidadeCompra.data_criacao.desc()
    ).all()
    if not necessidades:
        st.info("Nenhuma necessidade de compra foi gerada pelo PCP.")
        return

    st.dataframe(
        [{
            "ID": item.id_necessidade,
            "Material": item.item.descricao,
            "Produto": item.produto.descricao if item.produto else "—",
            "Necessário": float(item.quantidade_necessaria),
            "Disponível": float(item.saldo_disponivel),
            "Faltante": float(item.quantidade_faltante),
            "Status": item.status_necessidade,
            "Pedido": item.id_pedido_compra or "—",
        } for item in necessidades],
        use_container_width=True,
        hide_index=True,
    )

    pendentes = [item for item in necessidades if item.status_necessidade == "PENDENTE"]
    fornecedores = db.query(Fornecedor).order_by(Fornecedor.razao_social).all()
    if not pendentes:
        st.info("Não há necessidades pendentes para transformar em pedido.")
        return
    if not fornecedores:
        st.warning("Cadastre um fornecedor no Módulo de Cadastros para atender as necessidades pendentes.")
        return

    necessidade_map = {item.id_necessidade: item for item in pendentes}
    fornecedor_map = {item.id_fornecedor: item for item in fornecedores}
    selecionadas = st.multiselect(
        "Necessidades que entrarão no pedido",
        list(necessidade_map),
        format_func=lambda valor: (
            f"#{valor} — {necessidade_map[valor].item.descricao}: "
            f"{necessidade_map[valor].quantidade_faltante} "
            f"{necessidade_map[valor].item.unidade_medida}"
        ),
    )
    with st.form("pedido_por_necessidades"):
        fornecedor_id = st.selectbox(
            "Fornecedor",
            list(fornecedor_map),
            format_func=lambda valor: fornecedor_map[valor].razao_social,
        )
        custos = {}
        ids_itens = sorted({necessidade_map[item].id_item for item in selecionadas})
        for id_item in ids_itens:
            material = necessidade_map[next(
                chave for chave in selecionadas if necessidade_map[chave].id_item == id_item
            )].item
            custos[id_item] = st.number_input(
                f"Custo unitário de {material.descricao} (R$)",
                min_value=0.0,
                value=float(material.custo_medio or 0),
                key=f"custo_necessidade_{id_item}",
            )
        gerar = st.form_submit_button("Gerar pedido de compra", type="primary", use_container_width=True)
    if gerar:
        try:
            pedido = criar_pedido_por_necessidades(
                db, fornecedor_id, selecionadas, custos, usuario_atual.id_usuario
            )
            st.success(f"Pedido de compra #{pedido.id_pedido_compra} criado.")
            st.rerun()
        except Exception as erro:
            st.error(str(erro))


def render_compras(usuario_atual):
    render_cabecalho(
        "Compras",
        "Emita e gerencie pedidos de compra e receba materiais no estoque.",
    )
    db = SessionLocal()
    try:
        aba_necessidades, aba_novo, aba_gestao = st.tabs(
            ["Necessidades do PCP", "Novo pedido", "Acompanhar pedidos"]
        )
        with aba_necessidades:
            _necessidades_compra(db, usuario_atual)
        with aba_novo:
            _novo_pedido(db, usuario_atual)
        with aba_gestao:
            _gerenciar_pedidos(db, usuario_atual)
    finally:
        db.close()