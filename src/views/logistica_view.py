from datetime import date

import streamlit as st

from src.database.connection import SessionLocal
from src.database.models.logistica import Entrega, Veiculo
from src.services.logistica_service import (
    STATUS_ENTREGA_VALIDOS,
    configurar_rastreamento_externo,
    criar_rota_entrega,
    criar_veiculo,
    finalizar_rota,
    iniciar_rota,
    listar_devolucoes,
    listar_entregas,
    listar_rotas,
    receber_devolucao,
    registrar_comprovante_entrega,
    registrar_evento_rastreamento,
    solicitar_devolucao,
)
from src.views.components.ui_components import render_cabecalho


def _nome_entrega(entrega: Entrega) -> str:
    pedido = entrega.pedidos[0] if entrega.pedidos else None
    cliente = pedido.cliente if pedido else None
    return (
        f"Entrega #{entrega.id_entrega} — Pedido #{pedido.id_pedido_venda if pedido else '—'} "
        f"— {cliente.razao_social if cliente else 'Sem cliente'}"
    )


def _endereco_entrega(entrega: Entrega) -> str:
    pedido = entrega.pedidos[0] if entrega.pedidos else None
    cliente = pedido.cliente if pedido else None
    if cliente is None:
        return "Endereço não informado"
    return (
        f"{cliente.rua or '—'}, {cliente.numero or 'S/N'} — {cliente.bairro or '—'}, "
        f"{cliente.cidade or '—'}/{cliente.uf or '—'} — CEP {cliente.cep or '—'}"
    )


def _painel_rastreamento(db, usuario_atual):
    col1, col2 = st.columns([2, 1])
    filtro = col1.selectbox(
        "Status da entrega", ["Todas"] + list(STATUS_ENTREGA_VALIDOS),
        key="logistica_filtro_status",
    )
    somente_atrasadas = col2.checkbox("Somente atrasadas")
    entregas = listar_entregas(db, None if filtro == "Todas" else filtro)
    if somente_atrasadas:
        entregas = [
            item
            for item in entregas
            if item.data_previsao.date() < date.today()
            and item.status_logistica not in {"Entregue", "Devolvido"}
        ]
    if not entregas:
        st.info("Nenhuma entrega encontrada.")
        return
    st.dataframe(
        [
            {
                "Entrega": item.id_entrega,
                "Pedido": item.pedidos[0].id_pedido_venda if item.pedidos else "—",
                "Cliente": (
                    item.pedidos[0].cliente.razao_social
                    if item.pedidos and item.pedidos[0].cliente
                    else "—"
                ),
                "Previsão": item.data_previsao.strftime("%d/%m/%Y"),
                "Status": item.status_logistica,
                "Rastreio": item.rastreamento.codigo_rastreio if item.rastreamento else "—",
            }
            for item in entregas
        ],
        use_container_width=True,
        hide_index=True,
    )
    mapa = {item.id_entrega: item for item in entregas}
    id_entrega = st.selectbox(
        "Entrega para acompanhamento",
        list(mapa),
        format_func=lambda valor: _nome_entrega(mapa[valor]),
        key="rastreamento_entrega",
    )
    entrega = mapa[id_entrega]
    st.caption(_endereco_entrega(entrega))
    if entrega.rastreamento:
        referencia = entrega.rastreamento
        st.info(
            f"{referencia.transportadora or 'Transportadora'} — código "
            f"{referencia.codigo_rastreio}"
        )
        if referencia.url_rastreamento:
            st.link_button("Abrir rastreamento externo", referencia.url_rastreamento)

    with st.expander("Configurar rastreamento externo"):
        with st.form(f"rastreio_externo_{id_entrega}"):
            col3, col4 = st.columns(2)
            transportadora = col3.text_input(
                "Transportadora",
                value=entrega.rastreamento.transportadora or "" if entrega.rastreamento else "",
            )
            codigo = col4.text_input(
                "Código de rastreamento",
                value=entrega.rastreamento.codigo_rastreio if entrega.rastreamento else "",
            )
            url = st.text_input(
                "URL pública de rastreamento",
                value=entrega.rastreamento.url_rastreamento or "" if entrega.rastreamento else "",
            )
            salvar = st.form_submit_button("Salvar rastreamento", type="primary")
        if salvar:
            try:
                configurar_rastreamento_externo(
                    db,
                    id_entrega,
                    codigo,
                    usuario_atual.id_usuario,
                    transportadora,
                    url,
                )
                st.success("Rastreamento externo atualizado.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))

    with st.form(f"evento_rastreamento_{id_entrega}", clear_on_submit=True):
        st.markdown("#### Registrar etapa de rastreamento")
        col5, col6 = st.columns(2)
        status = col5.selectbox("Novo status", STATUS_ENTREGA_VALIDOS)
        localizacao = col6.text_input("Localização")
        descricao = st.text_input("Descrição do evento")
        salvar_evento = st.form_submit_button("Registrar evento", type="primary")
    if salvar_evento:
        try:
            registrar_evento_rastreamento(
                db,
                id_entrega,
                status,
                usuario_atual.id_usuario,
                descricao,
                localizacao,
            )
            st.success("Evento registrado.")
            st.rerun()
        except Exception as erro:
            st.error(str(erro))

    if entrega.eventos_rastreamento:
        st.markdown("#### Linha do tempo")
        st.dataframe(
            [
                {
                    "Data": item.data_evento.strftime("%d/%m/%Y %H:%M"),
                    "Status": item.status,
                    "Localização": item.localizacao or "—",
                    "Descrição": item.descricao or "—",
                }
                for item in entrega.eventos_rastreamento
            ],
            use_container_width=True,
            hide_index=True,
        )


def _rotas_e_veiculos(db, usuario_atual):
    with st.expander("Cadastrar veículo"):
        with st.form("novo_veiculo", clear_on_submit=True):
            col1, col2 = st.columns(2)
            placa = col1.text_input("Placa *")
            descricao = col2.text_input("Descrição/modelo *")
            col3, col4 = st.columns(2)
            motorista = col3.text_input("Motorista")
            capacidade = col4.number_input(
                "Capacidade (kg) *", min_value=0.01, value=500.0
            )
            cadastrar = st.form_submit_button("Cadastrar veículo", type="primary")
        if cadastrar:
            try:
                criar_veiculo(
                    db,
                    placa,
                    descricao,
                    capacidade,
                    usuario_atual.id_usuario,
                    motorista,
                )
                st.success("Veículo cadastrado.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))

    veiculos = db.query(Veiculo).filter(Veiculo.ativo == "S").order_by(Veiculo.placa).all()
    entregas = [
        item
        for item in listar_entregas(db)
        if item.status_logistica not in {"Entregue", "Devolvido"}
        and not any(
            parada.rota.status_rota in {"PLANEJADA", "EM_ROTA"}
            for parada in item.paradas_rota
        )
    ]
    st.markdown("### Planejar rota")
    if not veiculos or not entregas:
        st.info("Cadastre um veículo e mantenha entregas disponíveis para montar uma rota.")
    else:
        veiculo_map = {item.id_veiculo: item for item in veiculos}
        entrega_map = {item.id_entrega: item for item in entregas}
        selecionadas = st.multiselect(
            "Entregas em ordem de parada",
            list(entrega_map),
            format_func=lambda valor: _nome_entrega(entrega_map[valor]),
            key="rota_entregas",
        )
        with st.form("nova_rota"):
            col5, col6, col7 = st.columns(3)
            descricao_rota = col5.text_input("Descrição da rota")
            data_rota = col6.date_input("Data planejada", date.today())
            id_veiculo = col7.selectbox(
                "Veículo",
                list(veiculo_map),
                format_func=lambda valor: (
                    f"{veiculo_map[valor].placa} — {veiculo_map[valor].descricao} "
                    f"({veiculo_map[valor].capacidade_kg} kg)"
                ),
            )
            linhas = []
            for sequencia, id_item in enumerate(selecionadas, start=1):
                st.markdown(f"**{sequencia}. {_nome_entrega(entrega_map[id_item])}**")
                col8, col9 = st.columns(2)
                peso = col8.number_input(
                    "Peso estimado (kg)",
                    min_value=0.0,
                    value=0.0,
                    key=f"rota_peso_{id_item}",
                )
                observacao = col9.text_input(
                    "Observação", key=f"rota_obs_{id_item}"
                )
                linhas.append(
                    {
                        "id_entrega": id_item,
                        "peso_estimado_kg": peso,
                        "observacao": observacao,
                    }
                )
            criar = st.form_submit_button("Criar rota", type="primary")
        if criar:
            try:
                criar_rota_entrega(
                    db,
                    descricao_rota,
                    data_rota,
                    id_veiculo,
                    linhas,
                    usuario_atual.id_usuario,
                )
                st.success("Rota criada.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))

    rotas = listar_rotas(db)
    if not rotas:
        return
    st.markdown("### Rotas cadastradas")
    rota_map = {item.id_rota: item for item in rotas}
    id_rota = st.selectbox(
        "Rota",
        list(rota_map),
        format_func=lambda valor: (
            f"#{valor} — {rota_map[valor].descricao} — {rota_map[valor].status_rota}"
        ),
    )
    rota = rota_map[id_rota]
    st.dataframe(
        [
            {
                "Seq.": item.sequencia,
                "Entrega": item.id_entrega,
                "Destino": _endereco_entrega(item.entrega),
                "Peso (kg)": float(item.peso_estimado_kg),
                "Status": item.status_parada,
            }
            for item in rota.paradas
        ],
        use_container_width=True,
        hide_index=True,
    )
    col10, col11 = st.columns(2)
    if rota.status_rota == "PLANEJADA" and col10.button("Iniciar rota", type="primary"):
        try:
            iniciar_rota(db, id_rota, usuario_atual.id_usuario)
            st.success("Rota iniciada e entregas atualizadas para Em rota.")
            st.rerun()
        except Exception as erro:
            st.error(str(erro))
    if rota.status_rota == "EM_ROTA" and col11.button("Finalizar rota"):
        try:
            finalizar_rota(db, id_rota, usuario_atual.id_usuario)
            st.success("Rota finalizada.")
            st.rerun()
        except Exception as erro:
            st.error(str(erro))


def _comprovantes(db, usuario_atual):
    entregas = listar_entregas(db)
    if not entregas:
        st.info("Nenhuma entrega cadastrada.")
        return
    mapa = {item.id_entrega: item for item in entregas}
    id_entrega = st.selectbox(
        "Entrega",
        list(mapa),
        format_func=lambda valor: _nome_entrega(mapa[valor]),
        key="comprovante_entrega",
    )
    entrega = mapa[id_entrega]
    if entrega.comprovante:
        comprovante = entrega.comprovante
        st.success(
            f"Entrega recebida por {comprovante.nome_recebedor} em "
            f"{comprovante.data_recebimento.strftime('%d/%m/%Y %H:%M')}."
        )
        st.write(f"Assinatura declarada: **{comprovante.assinatura_recebedor}**")
        if comprovante.conteudo_arquivo:
            st.download_button(
                "Baixar comprovante",
                comprovante.conteudo_arquivo,
                file_name=comprovante.nome_arquivo or "comprovante",
                mime=comprovante.tipo_arquivo,
            )
    with st.form(f"comprovante_{id_entrega}"):
        col1, col2 = st.columns(2)
        recebedor = col1.text_input("Nome do recebedor *")
        documento = col2.text_input("Documento do recebedor")
        assinatura = st.text_input(
            "Assinatura digital declarada *",
            help="Digite o nome usado pelo recebedor para confirmar a entrega.",
        )
        arquivo = st.file_uploader(
            "Foto ou PDF do comprovante", type=["png", "jpg", "jpeg", "pdf"]
        )
        observacao = st.text_area("Observação")
        registrar = st.form_submit_button("Registrar comprovante", type="primary")
    if registrar:
        try:
            registrar_comprovante_entrega(
                db,
                id_entrega,
                recebedor,
                assinatura,
                usuario_atual.id_usuario,
                documento,
                arquivo.name if arquivo else None,
                arquivo.type if arquivo else None,
                arquivo.getvalue() if arquivo else None,
                observacao,
            )
            st.success("Comprovante armazenado e entrega concluída.")
            st.rerun()
        except Exception as erro:
            st.error(str(erro))


def _devolucoes(db, usuario_atual):
    entregas = [item for item in listar_entregas(db) if item.pedidos]
    if entregas:
        mapa = {item.id_entrega: item for item in entregas}
        id_entrega = st.selectbox(
            "Entrega para devolução",
            list(mapa),
            format_func=lambda valor: _nome_entrega(mapa[valor]),
            key="devolucao_entrega",
        )
        entrega = mapa[id_entrega]
        itens_vendidos = {}
        for pedido in entrega.pedidos:
            for linha in pedido.itens:
                itens_vendidos[linha.id_item] = linha
        selecionados = st.multiselect(
            "Itens devolvidos",
            list(itens_vendidos),
            format_func=lambda valor: itens_vendidos[valor].item.descricao,
            key=f"devolucao_itens_{id_entrega}",
        )
        with st.form(f"nova_devolucao_{id_entrega}"):
            motivo = st.text_input("Motivo *")
            linhas = []
            for id_item in selecionados:
                vendido = itens_vendidos[id_item]
                st.markdown(f"**{vendido.item.descricao}**")
                col1, col2, col3 = st.columns(3)
                quantidade = col1.number_input(
                    "Quantidade",
                    min_value=0.01,
                    max_value=float(vendido.quantidade_vendida),
                    value=float(vendido.quantidade_vendida),
                    key=f"devolucao_qtd_{id_entrega}_{id_item}",
                )
                condicao = col2.selectbox(
                    "Condição",
                    ["INTEGRO", "AVARIADO", "INUTILIZADO"],
                    key=f"devolucao_condicao_{id_entrega}_{id_item}",
                )
                reintegrar = col3.checkbox(
                    "Voltar ao estoque",
                    value=condicao == "INTEGRO",
                    disabled=condicao != "INTEGRO",
                    key=f"devolucao_reintegrar_{id_entrega}_{id_item}",
                )
                linhas.append(
                    {
                        "id_item": id_item,
                        "quantidade": quantidade,
                        "condicao_item": condicao,
                        "reintegrar_estoque": reintegrar,
                    }
                )
            observacao = st.text_area("Observação")
            solicitar = st.form_submit_button("Solicitar devolução", type="primary")
        if solicitar:
            try:
                solicitar_devolucao(
                    db,
                    id_entrega,
                    motivo,
                    linhas,
                    usuario_atual.id_usuario,
                    observacao,
                )
                st.success("Devolução registrada.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))

    devolucoes = listar_devolucoes(db)
    if not devolucoes:
        st.info("Nenhuma devolução cadastrada.")
        return
    st.markdown("### Devoluções")
    st.dataframe(
        [
            {
                "ID": item.id_devolucao,
                "Entrega": item.id_entrega,
                "Motivo": item.motivo,
                "Status": item.status_devolucao,
                "Solicitação": item.data_solicitacao,
                "Itens": len(item.itens),
            }
            for item in devolucoes
        ],
        use_container_width=True,
        hide_index=True,
    )
    pendentes = [
        item for item in devolucoes if item.status_devolucao in {"SOLICITADA", "EM_TRANSITO"}
    ]
    if pendentes:
        mapa_devolucao = {item.id_devolucao: item for item in pendentes}
        id_devolucao = st.selectbox(
            "Devolução para recebimento",
            list(mapa_devolucao),
            format_func=lambda valor: (
                f"#{valor} — Entrega #{mapa_devolucao[valor].id_entrega} — "
                f"{mapa_devolucao[valor].motivo}"
            ),
        )
        if st.button("Receber devolução", type="primary"):
            try:
                receber_devolucao(db, id_devolucao, usuario_atual.id_usuario)
                st.success("Devolução recebida e itens íntegros reintegrados ao estoque.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))


def render_logistica(usuario_atual):
    render_cabecalho(
        "Gestão Logística",
        "Planeje rotas, acompanhe entregas e controle comprovantes e devoluções.",
    )
    db = SessionLocal()
    try:
        abas = st.tabs(
            ["Entregas e rastreamento", "Rotas e veículos", "Comprovantes", "Devoluções"]
        )
        with abas[0]:
            _painel_rastreamento(db, usuario_atual)
        with abas[1]:
            _rotas_e_veiculos(db, usuario_atual)
        with abas[2]:
            _comprovantes(db, usuario_atual)
        with abas[3]:
            _devolucoes(db, usuario_atual)
    finally:
        db.close()
