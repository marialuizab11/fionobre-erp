from datetime import date, timedelta

import streamlit as st

from src.database.connection import SessionLocal
from src.database.models.cadastros import Item
from src.database.models.compras import Fornecedor, NecessidadeCompra
from src.services.compra_service import (
    cancelar_compra,
    confirmar_compra,
    criar_fornecedor,
    criar_pedido_por_necessidades,
    criar_pedido_compra,
    listar_pedidos_compra,
    receber_compra,
)
from src.views.components.ui_components import render_cabecalho


def _cadastro_fornecedor(db, usuario_atual):
    with st.expander("Cadastrar fornecedor"):
        with st.form("novo_fornecedor", clear_on_submit=True):
            razao = st.text_input("Razão social *")
            documento = st.text_input("CPF/CNPJ *")
            col1, col2 = st.columns(2)
            email = col1.text_input("E-mail")
            telefone = col2.text_input("Telefone")
            col3, col4, col5 = st.columns([2, 3, 1])
            cep = col3.text_input("CEP")
            rua = col4.text_input("Rua")
            numero = col5.text_input("Número")
            col6, col7, col8 = st.columns([2, 2, 1])
            bairro = col6.text_input("Bairro")
            cidade = col7.text_input("Cidade")
            uf = col8.text_input("UF", max_chars=2)
            salvar = st.form_submit_button("Cadastrar fornecedor", type="primary")
        if salvar:
            try:
                criar_fornecedor(
                    db, razao, documento, usuario_atual.id_usuario,
                    email=email, telefone=telefone, cep=cep, rua=rua,
                    numero=numero, bairro=bairro, cidade=cidade, uf=uf,
                )
                st.success("Fornecedor cadastrado.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))


def _novo_pedido(db, usuario_atual):
    fornecedores = db.query(Fornecedor).order_by(Fornecedor.razao_social).all()
    itens = db.query(Item).order_by(Item.descricao).all()
    if not fornecedores or not itens:
        st.info("Cadastre pelo menos um fornecedor e um item antes de criar uma compra.")
        return

    fornecedor_map = {f.id_fornecedor: f for f in fornecedores}
    item_map = {i.id_item: i for i in itens}
    fornecedor_id = st.selectbox(
        "Fornecedor",
        list(fornecedor_map),
        format_func=lambda valor: fornecedor_map[valor].razao_social,
    )
    itens_ids = st.multiselect(
        "Itens da compra",
        list(item_map),
        format_func=lambda valor: (
            f"{item_map[valor].descricao} — saldo {item_map[valor].saldo_estoque} "
            f"{item_map[valor].unidade_medida}"
        ),
    )
    with st.form("novo_pedido_compra"):
        linhas = []
        for item_id in itens_ids:
            item = item_map[item_id]
            st.markdown(f"**{item.descricao}**")
            col1, col2 = st.columns(2)
            quantidade = col1.number_input(
                "Quantidade", min_value=0.01, value=1.0, key=f"compra_qtd_{item_id}"
            )
            custo = col2.number_input(
                "Custo unitário (R$)", min_value=0.0,
                value=float(item.custo_medio or 0), key=f"compra_custo_{item_id}",
            )
            linhas.append({"id_item": item_id, "quantidade": quantidade, "custo_unitario": custo})
        criar = st.form_submit_button("Criar pedido de compra", type="primary")
    if criar:
        try:
            pedido = criar_pedido_compra(db, fornecedor_id, linhas, usuario_atual.id_usuario)
            st.success(f"Pedido de compra #{pedido.id_pedido_compra} criado.")
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
        "Pedido",
        list(pedido_map),
        format_func=lambda valor: (
            f"#{valor} — {pedido_map[valor].fornecedor.razao_social} — "
            f"{pedido_map[valor].status_compra} — R$ {pedido_map[valor].valor_total_pedido:.2f}"
        ),
    )
    pedido = pedido_map[pedido_id]
    st.dataframe(
        [{
            "Item": linha.item.descricao,
            "Quantidade": float(linha.quantidade_comprada),
            "Custo unitário": float(linha.custo_unitario),
            "Subtotal": float(linha.quantidade_comprada * linha.custo_unitario),
        } for linha in pedido.itens],
        use_container_width=True,
        hide_index=True,
    )

    if pedido.status_compra == "Criado":
        if st.button("Confirmar pedido", type="primary"):
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
        if st.button("Registrar recebimento", type="primary"):
            try:
                receber_compra(db, pedido_id, vencimento, usuario_atual.id_usuario)
                st.success("Compra recebida; estoque e financeiro atualizados.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))

    if pedido.status_compra != "Cancelado":
        with st.form(f"cancelar_compra_{pedido_id}"):
            justificativa = st.text_area("Justificativa para cancelamento")
            cancelar = st.form_submit_button("Cancelar pedido")
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
        st.warning("Cadastre um fornecedor para atender as necessidades pendentes.")
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
        gerar = st.form_submit_button("Gerar pedido de compra", type="primary")
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
        "Cadastre fornecedores, emita pedidos e receba materiais no estoque.",
    )
    db = SessionLocal()
    try:
        _cadastro_fornecedor(db, usuario_atual)
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
