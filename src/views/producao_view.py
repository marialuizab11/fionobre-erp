from datetime import date, timedelta

import streamlit as st

from src.database.connection import SessionLocal
from src.database.models.cadastros import Item
from src.database.models.producao import CentroProducao
from src.services.compra_service import gerar_necessidades_compra
from src.services.producao_service import (
    atualizar_operacao_ordem,
    calcular_necessidade_materiais,
    cancelar_ordem_producao,
    configurar_capacidade_centro,
    consultar_carga_centros,
    criar_centro_producao,
    criar_ordem_producao,
    finalizar_producao,
    iniciar_producao,
    listar_ordens_producao,
    obter_ficha_tecnica,
    obter_roteiro_producao,
    registrar_consumo,
    registrar_inspecao_qualidade,
    registrar_perda,
    salvar_ficha_tecnica,
    salvar_roteiro_producao,
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

    centros = db.query(CentroProducao).filter(CentroProducao.ativo == "S").all()
    if centros:
        with st.expander("Configurar capacidade dos centros"):
            mapa = {item.id_centro_producao: item for item in centros}
            id_centro = st.selectbox(
                "Centro",
                list(mapa),
                format_func=lambda valor: mapa[valor].nome,
                key="capacidade_centro",
            )
            atual = mapa[id_centro].capacidade
            with st.form(f"capacidade_{id_centro}"):
                col1, col2 = st.columns(2)
                horas = col1.number_input(
                    "Horas disponíveis por dia",
                    min_value=0.5,
                    max_value=24.0,
                    value=float(atual.horas_disponiveis_dia) if atual else 8.0,
                    step=0.5,
                )
                inicio = col2.text_input(
                    "Início do expediente",
                    value=atual.hora_inicio_expediente if atual else "08:00",
                )
                dias = st.multiselect(
                    "Dias de trabalho",
                    options=list(range(7)),
                    default=(
                        [int(item) for item in atual.dias_uteis.split(",")]
                        if atual
                        else [0, 1, 2, 3, 4]
                    ),
                    format_func=lambda valor: [
                        "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"
                    ][valor],
                )
                salvar_capacidade = st.form_submit_button(
                    "Salvar capacidade", type="primary"
                )
            if salvar_capacidade:
                try:
                    configurar_capacidade_centro(
                        db,
                        id_centro,
                        horas,
                        usuario_atual.id_usuario,
                        inicio,
                        ",".join(str(item) for item in dias),
                    )
                    st.success("Capacidade atualizada.")
                    st.rerun()
                except Exception as erro:
                    st.error(str(erro))


def _roteiros_e_capacidade(db, usuario_atual):
    produtos = db.query(Item).filter(Item.tipo_item == "PRODUTO_ACABADO").all()
    centros = db.query(CentroProducao).filter(CentroProducao.ativo == "S").all()
    centros_capazes = [item for item in centros if item.capacidade]
    if not produtos or not centros_capazes:
        st.info("Cadastre produtos e configure a capacidade de pelo menos um centro.")
        return
    produto_map = {item.id_item: item for item in produtos}
    centro_map = {item.id_centro_producao: item for item in centros_capazes}
    produto_id = st.selectbox(
        "Produto do roteiro",
        list(produto_map),
        format_func=lambda valor: produto_map[valor].descricao,
        key="roteiro_produto",
    )
    roteiro = obter_roteiro_producao(db, produto_id)
    quantidade_operacoes = st.number_input(
        "Quantidade de operações",
        min_value=1,
        max_value=10,
        value=len(roteiro.operacoes) if roteiro else 1,
        step=1,
        key=f"roteiro_qtd_{produto_id}",
    )
    with st.form(f"roteiro_form_{produto_id}_{quantidade_operacoes}"):
        descricao = st.text_input(
            "Descrição do roteiro", value=roteiro.descricao or "" if roteiro else ""
        )
        operacoes = []
        for indice in range(int(quantidade_operacoes)):
            atual = roteiro.operacoes[indice] if roteiro and indice < len(roteiro.operacoes) else None
            st.markdown(f"#### Operação {indice + 1}")
            col1, col2 = st.columns(2)
            nome = col1.text_input(
                "Nome da operação",
                value=atual.nome_operacao if atual else "",
                key=f"roteiro_nome_{produto_id}_{indice}",
            )
            centro = col2.selectbox(
                "Centro de produção",
                list(centro_map),
                index=(
                    list(centro_map).index(atual.id_centro_producao)
                    if atual and atual.id_centro_producao in centro_map
                    else 0
                ),
                format_func=lambda valor: centro_map[valor].nome,
                key=f"roteiro_centro_{produto_id}_{indice}",
            )
            col3, col4, col5 = st.columns(3)
            recurso = col3.text_input(
                "Recurso/máquina",
                value=atual.recurso or "" if atual else "",
                key=f"roteiro_recurso_{produto_id}_{indice}",
            )
            setup = col4.number_input(
                "Setup (horas)",
                min_value=0.0,
                value=float(atual.tempo_setup_horas) if atual else 0.0,
                step=0.25,
                key=f"roteiro_setup_{produto_id}_{indice}",
            )
            unitario = col5.number_input(
                "Tempo por unidade (horas)",
                min_value=0.0,
                value=float(atual.tempo_unitario_horas) if atual else 0.1,
                step=0.05,
                format="%.4f",
                key=f"roteiro_unitario_{produto_id}_{indice}",
            )
            instrucoes = st.text_input(
                "Instruções",
                value=atual.instrucoes or "" if atual else "",
                key=f"roteiro_instrucao_{produto_id}_{indice}",
            )
            operacoes.append(
                {
                    "nome_operacao": nome,
                    "id_centro_producao": centro,
                    "recurso": recurso,
                    "tempo_setup_horas": setup,
                    "tempo_unitario_horas": unitario,
                    "instrucoes": instrucoes,
                }
            )
        salvar = st.form_submit_button("Salvar roteiro", type="primary")
    if salvar:
        try:
            salvar_roteiro_producao(
                db, produto_id, operacoes, usuario_atual.id_usuario, descricao
            )
            st.success("Roteiro salvo.")
            st.rerun()
        except Exception as erro:
            st.error(str(erro))

    st.markdown("### Ocupação dos centros")
    col1, col2 = st.columns(2)
    inicio = col1.date_input("Início", date.today(), key="capacidade_inicio")
    fim = col2.date_input(
        "Fim", date.today() + timedelta(days=14), key="capacidade_fim"
    )
    carga = consultar_carga_centros(db, inicio, fim)
    if carga:
        st.dataframe(
            [
                {
                    "Data": item["data"].strftime("%d/%m/%Y"),
                    "Centro": item["centro"],
                    "Capacidade (h)": float(item["capacidade"]),
                    "Alocado (h)": float(item["alocado"]),
                    "Disponível (h)": float(item["disponivel"]),
                    "Ocupação (%)": float(item["ocupacao_percentual"]),
                }
                for item in carga
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhuma capacidade foi alocada nesse período.")


def _fichas_tecnicas(db, usuario_atual):
    produtos = db.query(Item).filter(Item.tipo_item == "PRODUTO_ACABADO").all()
    insumos = db.query(Item).filter(Item.tipo_item != "PRODUTO_ACABADO").all()
    if not produtos or not insumos:
        st.info("Cadastre um produto acabado e ao menos uma matéria-prima ou insumo.")
        return

    if "form_ficha_reset_counter" not in st.session_state:
        st.session_state["form_ficha_reset_counter"] = 0

    produto_map = {item.id_item: item for item in produtos}
    insumo_map = {item.id_item: item for item in insumos}
    
    produto_id = st.selectbox(
        "Produto da ficha técnica",
        list(produto_map),
        format_func=lambda valor: produto_map[valor].descricao,
        key=f"ficha_produto_{st.session_state['form_ficha_reset_counter']}",
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
        key=f"ficha_componentes_{produto_id}_{st.session_state['form_ficha_reset_counter']}",
    )
    
    atuais = {
        item.id_item_insumo: float(item.quantidade_por_unidade)
        for item in ficha_atual.componentes
    } if ficha_atual else {}

    with st.form(f"form_ficha_{produto_id}_{st.session_state['form_ficha_reset_counter']}"):
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
                key=f"ficha_qtd_{produto_id}_{insumo_id}_{st.session_state['form_ficha_reset_counter']}",
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
            st.session_state["form_ficha_reset_counter"] += 1
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
    roteiro = obter_roteiro_producao(db, produto_id)
    data_inicio_planejada = None
    if roteiro:
        data_inicio_planejada = st.date_input(
            "Início planejado", value=date.today(), key=f"inicio_ordem_{produto_id}"
        )
        carga_estimada = sum(
            float(item.tempo_setup_horas)
            + float(item.tempo_unitario_horas) * float(quantidade)
            for item in roteiro.operacoes
        )
        st.info(
            f"Roteiro com {len(roteiro.operacoes)} operação(ões) e "
            f"{carga_estimada:.2f} hora(s) estimadas. A agenda respeitará a capacidade."
        )
    else:
        st.warning(
            "Este produto ainda não possui roteiro. A ordem será criada no modo legado, "
            "sem agendamento de capacidade."
        )

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
                db,
                centro_id,
                produto_id,
                quantidade,
                usuario_atual.id_usuario,
                data_inicio_planejada=data_inicio_planejada,
                id_roteiro=roteiro.id_roteiro if roteiro else None,
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


def _controle_qualidade(db, ordem, usuario_atual):
    st.markdown("#### Controle de qualidade")
    operacao_map = {item.id_ordem_operacao: item for item in ordem.operacoes}
    with st.form(f"qualidade_{ordem.id_ordem_producao}"):
        col1, col2, col3 = st.columns(3)
        etapa = col1.selectbox("Etapa", ["DURANTE", "FINAL"])
        resultado = col2.selectbox(
            "Resultado", ["APROVADO", "CONDICIONAL", "REPROVADO"]
        )
        id_operacao = col3.selectbox(
            "Operação relacionada",
            [None] + list(operacao_map),
            format_func=lambda valor: (
                "Inspeção geral"
                if valor is None
                else f"{operacao_map[valor].sequencia}. {operacao_map[valor].nome_operacao}"
            ),
        )
        col4, col5, col6 = st.columns(3)
        inspecionada = col4.number_input(
            "Quantidade inspecionada", min_value=0.01, value=float(ordem.quantidade_planejada)
        )
        aprovada = col5.number_input(
            "Quantidade aprovada", min_value=0.0, value=float(ordem.quantidade_planejada)
        )
        reprovada = col6.number_input("Quantidade reprovada", min_value=0.0, value=0.0)
        observacao = st.text_area("Observação da inspeção")
        registrar = st.form_submit_button("Registrar inspeção", type="primary")
    if registrar:
        try:
            registrar_inspecao_qualidade(
                db,
                ordem.id_ordem_producao,
                etapa,
                resultado,
                inspecionada,
                aprovada,
                reprovada,
                usuario_atual.id_usuario,
                observacao,
                id_operacao,
            )
            st.success("Inspeção registrada.")
            st.rerun()
        except Exception as erro:
            st.error(str(erro))
    if ordem.inspecoes_qualidade:
        st.dataframe(
            [
                {
                    "Data": item.data_inspecao,
                    "Etapa": item.etapa,
                    "Operação": item.ordem_operacao.nome_operacao if item.ordem_operacao else "Geral",
                    "Resultado": item.resultado,
                    "Inspecionada": float(item.quantidade_inspecionada),
                    "Aprovada": float(item.quantidade_aprovada),
                    "Reprovada": float(item.quantidade_reprovada),
                    "Observação": item.observacao or "—",
                }
                for item in ordem.inspecoes_qualidade
            ],
            use_container_width=True,
            hide_index=True,
        )

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

    if ordem.planejamento:
        st.markdown("#### Planejamento de capacidade e roteiro")
        col4, col5, col6 = st.columns(3)
        col4.metric(
            "Início planejado",
            ordem.planejamento.data_inicio_planejada.strftime("%d/%m/%Y %H:%M"),
        )
        col5.metric(
            "Fim planejado",
            ordem.planejamento.data_fim_planejada.strftime("%d/%m/%Y %H:%M"),
        )
        col6.metric("Carga total", f"{ordem.planejamento.carga_total_horas:.2f} h")
        st.dataframe(
            [
                {
                    "Seq.": item.sequencia,
                    "Operação": item.nome_operacao,
                    "Centro": item.centro.nome,
                    "Recurso": item.recurso or "—",
                    "Carga (h)": float(item.carga_horas),
                    "Início": item.inicio_planejado,
                    "Fim": item.fim_planejado,
                    "Status": item.status_operacao,
                }
                for item in ordem.operacoes
            ],
            use_container_width=True,
            hide_index=True,
        )
        em_execucao = next(
            (item for item in ordem.operacoes if item.status_operacao == "EM_EXECUCAO"),
            None,
        )
        if ordem.status_ordem == "Em Producao" and em_execucao:
            if st.button(
                f"Concluir operação: {em_execucao.nome_operacao}",
                key=f"concluir_operacao_{em_execucao.id_ordem_operacao}",
            ):
                try:
                    atualizar_operacao_ordem(
                        db,
                        em_execucao.id_ordem_operacao,
                        "CONCLUIDA",
                        usuario_atual.id_usuario,
                    )
                    st.success("Operação concluída; próxima etapa liberada.")
                    st.rerun()
                except Exception as erro:
                    st.error(str(erro))

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
        _controle_qualidade(db, ordem, usuario_atual)
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
        aba_ficha, aba_roteiro, aba_nova, aba_gestao = st.tabs(
            [
                "Fichas técnicas",
                "Roteiros e capacidade",
                "Nova ordem",
                "Acompanhar produção",
            ]
        )
        with aba_ficha:
            _fichas_tecnicas(db, usuario_atual)
        with aba_roteiro:
            _roteiros_e_capacidade(db, usuario_atual)
        with aba_nova:
            _nova_ordem(db, usuario_atual)
        with aba_gestao:
            _gerenciar_ordens(db, usuario_atual)
    finally:
        db.close()
