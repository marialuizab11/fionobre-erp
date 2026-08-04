import streamlit as st

from src.database.connection import SessionLocal
from src.database.models.cadastros import Item
from src.database.models.producao import CentroProducao
from src.services.compra_service import gerar_necessidades_compra
from src.services.producao_service import (
    calcular_necessidade_materiais,
    cancelar_ordem_producao,
    criar_centro_producao,
    criar_ordem_producao,
    finalizar_producao,
    iniciar_producao,
    listar_ordens_producao,
    obter_ficha_tecnica,
    registrar_consumo,
    registrar_perda,
    salvar_ficha_tecnica,
)
from src.views.components.ui_components import render_cabecalho


def _cadastro_centro(db, usuario_atual):
    with st.expander("Cadastrar centro de produção"):
        with st.form("novo_centro", clear_on_submit=True):
            nome = st.text_input("Nome *")
            descricao = st.text_area("Descrição")
            salvar = st.form_submit_button("Cadastrar centro", type="primary")
        if salvar:
            try:
                criar_centro_producao(db, nome, descricao, usuario_atual.id_usuario)
                st.success("Centro de produção cadastrado.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))


def _fichas_tecnicas(db, usuario_atual):
    produtos = db.query(Item).filter(Item.tipo_item == "PRODUTO_ACABADO").all()
    insumos = db.query(Item).filter(Item.tipo_item != "PRODUTO_ACABADO").all()
    if not produtos or not insumos:
        st.info("Cadastre um produto acabado e ao menos uma matéria-prima ou insumo.")
        return

    produto_map = {item.id_item: item for item in produtos}
    insumo_map = {item.id_item: item for item in insumos}
    produto_id = st.selectbox(
        "Produto da ficha técnica",
        list(produto_map),
        format_func=lambda valor: produto_map[valor].descricao,
        key="ficha_produto",
    )
    ficha_atual = obter_ficha_tecnica(db, produto_id)
    ids_atuais = [item.id_item_insumo for item in ficha_atual.componentes] if ficha_atual else []
    selecionados = st.multiselect(
        "Componentes",
        list(insumo_map),
        default=ids_atuais,
        format_func=lambda valor: (
            f"{insumo_map[valor].descricao} ({insumo_map[valor].unidade_medida})"
        ),
        key=f"ficha_componentes_{produto_id}",
    )
    atuais = {
        item.id_item_insumo: float(item.quantidade_por_unidade)
        for item in ficha_atual.componentes
    } if ficha_atual else {}

    with st.form(f"form_ficha_{produto_id}"):
        descricao = st.text_input(
            "Descrição da ficha",
            value=ficha_atual.descricao or "" if ficha_atual else "",
        )
        componentes = []
        for insumo_id in selecionados:
            insumo = insumo_map[insumo_id]
            quantidade = st.number_input(
                f"{insumo.descricao} por unidade de produto ({insumo.unidade_medida})",
                min_value=0.0001,
                value=atuais.get(insumo_id, 1.0),
                format="%.4f",
                key=f"ficha_qtd_{produto_id}_{insumo_id}",
            )
            componentes.append({
                "id_item_insumo": insumo_id,
                "quantidade_por_unidade": quantidade,
            })
        salvar = st.form_submit_button("Salvar ficha técnica", type="primary")
    if salvar:
        try:
            salvar_ficha_tecnica(
                db, produto_id, componentes, usuario_atual.id_usuario, descricao
            )
            st.success("Ficha técnica salva.")
            st.rerun()
        except Exception as erro:
            st.error(str(erro))

    if ficha_atual:
        st.markdown("#### Composição atual")
        st.dataframe(
            [{
                "Insumo": componente.insumo.descricao,
                "Quantidade por unidade": float(componente.quantidade_por_unidade),
                "Unidade": componente.insumo.unidade_medida,
            } for componente in ficha_atual.componentes],
            use_container_width=True,
            hide_index=True,
        )


def _nova_ordem(db, usuario_atual):
    centros = db.query(CentroProducao).filter(CentroProducao.ativo == "S").all()
    produtos = db.query(Item).filter(Item.tipo_item == "PRODUTO_ACABADO").all()
    if not centros or not produtos:
        st.info("Cadastre um centro de produção e um produto acabado para criar a ordem.")
        return
    centro_map = {c.id_centro_producao: c for c in centros}
    produto_map = {p.id_item: p for p in produtos}
    centro_id = st.selectbox(
        "Centro de produção", list(centro_map),
        format_func=lambda valor: centro_map[valor].nome,
    )
    produto_id = st.selectbox(
        "Produto acabado", list(produto_map),
        format_func=lambda valor: produto_map[valor].descricao,
    )
    quantidade = st.number_input("Quantidade planejada", min_value=0.01, value=1.0)

    pode_criar = False
    necessidades = []
    try:
        necessidades = calcular_necessidade_materiais(db, produto_id, quantidade)
        st.markdown("#### Necessidade calculada")
        st.dataframe(
            [{
                "Material": item["descricao"],
                "Por unidade": float(item["quantidade_por_unidade"]),
                "Necessário": float(item["quantidade_necessaria"]),
                "Estoque físico": float(item["saldo_fisico"]),
                "Já reservado": float(item["quantidade_reservada"]),
                "Disponível": float(item["saldo_disponivel"]),
                "Faltante": float(item["quantidade_faltante"]),
                "Unidade": item["unidade_medida"],
            } for item in necessidades],
            use_container_width=True,
            hide_index=True,
        )
        pode_criar = all(item["quantidade_faltante"] == 0 for item in necessidades)
        if not pode_criar:
            st.warning("Há materiais insuficientes. Receba uma compra antes de criar a ordem.")
            if st.button("Gerar necessidades de compra", type="primary"):
                try:
                    registros = gerar_necessidades_compra(
                        db, produto_id, necessidades, usuario_atual.id_usuario
                    )
                    st.success(f"{len(registros)} necessidade(s) encaminhada(s) para Compras.")
                    st.rerun()
                except Exception as erro:
                    st.error(str(erro))
    except ValueError as erro:
        st.warning(str(erro))

    criar = st.button("Criar ordem", type="primary", disabled=not pode_criar)
    if criar:
        try:
            ordem = criar_ordem_producao(
                db, centro_id, produto_id, quantidade, usuario_atual.id_usuario
            )
            st.success(f"Ordem de produção #{ordem.id_ordem_producao} criada.")
            st.rerun()
        except Exception as erro:
            st.error(str(erro))


def _apontar_producao(db, ordem, usuario_atual):
    ids_reservados = [
        reserva.id_item_insumo
        for reserva in ordem.reservas
        if reserva.status_reserva == "RESERVADA"
    ]
    insumos = db.query(Item).filter(Item.id_item.in_(ids_reservados)).all()
    if not insumos:
        st.warning("Não há matérias-primas ou insumos cadastrados.")
        return
    insumo_map = {i.id_item: i for i in insumos}
    with st.form(f"apontamento_{ordem.id_ordem_producao}"):
        insumo_id = st.selectbox(
            "Insumo", list(insumo_map),
            format_func=lambda valor: (
                f"{insumo_map[valor].descricao} — saldo {insumo_map[valor].saldo_estoque}"
            ),
        )
        tipo = st.radio("Tipo de apontamento", ["CONSUMO", "PERDA"], horizontal=True)
        quantidade = st.number_input("Quantidade apontada", min_value=0.01, value=1.0)
        registrar = st.form_submit_button("Registrar apontamento")
    if registrar:
        try:
            funcao = registrar_consumo if tipo == "CONSUMO" else registrar_perda
            funcao(db, ordem.id_ordem_producao, insumo_id, quantidade, usuario_atual.id_usuario)
            st.success("Apontamento registrado.")
            st.rerun()
        except Exception as erro:
            st.error(str(erro))

    with st.form(f"finalizar_{ordem.id_ordem_producao}"):
        produzida = st.number_input(
            "Quantidade efetivamente produzida", min_value=0.01,
            value=float(ordem.quantidade_planejada),
        )
        finalizar = st.form_submit_button("Finalizar produção", type="primary")
    if finalizar:
        try:
            finalizar_producao(db, ordem.id_ordem_producao, produzida, usuario_atual.id_usuario)
            st.success("Produção finalizada e estoque atualizado.")
            st.rerun()
        except Exception as erro:
            st.error(str(erro))


def _gerenciar_ordens(db, usuario_atual):
    ordens = listar_ordens_producao(db)
    if not ordens:
        st.info("Nenhuma ordem de produção cadastrada.")
        return
    ordem_map = {o.id_ordem_producao: o for o in ordens}
    ordem_id = st.selectbox(
        "Ordem de produção", list(ordem_map),
        format_func=lambda valor: (
            f"#{valor} — {ordem_map[valor].produto.descricao} — "
            f"{ordem_map[valor].status_ordem}"
        ),
    )
    ordem = ordem_map[ordem_id]
    col1, col2, col3 = st.columns(3)
    col1.metric("Planejado", float(ordem.quantidade_planejada))
    col2.metric("Produzido", float(ordem.quantidade_produzida or 0))
    col3.metric("Apontamentos", len(ordem.consumos))

    if ordem.reservas:
        st.markdown("#### Materiais reservados")
        st.dataframe(
            [{
                "Insumo": reserva.insumo.descricao,
                "Reservado": float(reserva.quantidade_reservada),
                "Consumido": float(reserva.quantidade_consumida or 0),
                "Unidade": reserva.insumo.unidade_medida,
                "Status": reserva.status_reserva,
            } for reserva in ordem.reservas],
            use_container_width=True,
            hide_index=True,
        )

    if ordem.consumos:
        st.dataframe(
            [{
                "Insumo": registro.insumo.descricao,
                "Tipo": registro.tipo_registro,
                "Quantidade": float(registro.quantidade),
                "Data": registro.data_registro,
            } for registro in ordem.consumos],
            use_container_width=True,
            hide_index=True,
        )

    if ordem.status_ordem == "Criado":
        if st.button("Iniciar produção", type="primary"):
            try:
                iniciar_producao(db, ordem_id, usuario_atual.id_usuario)
                st.success("Produção iniciada.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))
    elif ordem.status_ordem == "Em Producao":
        _apontar_producao(db, ordem, usuario_atual)
    else:
        st.info("Esta ordem já foi finalizada ou cancelada.")

    if ordem.status_ordem not in ["Finalizado", "Cancelado"]:
        with st.form(f"cancelar_ordem_{ordem_id}"):
            justificativa = st.text_area("Justificativa para cancelar a ordem")
            cancelar = st.form_submit_button("Cancelar ordem")
        if cancelar:
            try:
                cancelar_ordem_producao(
                    db, ordem_id, justificativa, usuario_atual.id_usuario
                )
                st.success("Ordem cancelada e materiais liberados.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))


def render_producao(usuario_atual):
    render_cabecalho(
        "PCP e Produção",
        "Planeje ordens, registre consumo e incorpore produtos acabados ao estoque.",
    )
    db = SessionLocal()
    try:
        _cadastro_centro(db, usuario_atual)
        aba_ficha, aba_nova, aba_gestao = st.tabs(
            ["Fichas técnicas", "Nova ordem", "Acompanhar produção"]
        )
        with aba_ficha:
            _fichas_tecnicas(db, usuario_atual)
        with aba_nova:
            _nova_ordem(db, usuario_atual)
        with aba_gestao:
            _gerenciar_ordens(db, usuario_atual)
    finally:
        db.close()
