import streamlit as st

from src.database.connection import SessionLocal
from src.services.auth_service import PERFIS_PADRAO, PERMISSOES_PADRAO
from src.services.usuario_service import (
    alterar_perfil_usuario,
    alterar_status_usuario,
    atualizar_perfil,
    atualizar_permissao,
    cadastrar_usuario,
    criar_perfil,
    criar_permissao,
    excluir_perfil,
    excluir_permissao,
    listar_logs,
    listar_perfis,
    listar_permissoes,
    listar_usuarios,
)
from src.views.components.ui_components import render_cabecalho, render_dataframe_padrao


def _recarregar_contexto_usuario() -> None:
    st.session_state.pop("usuario_contexto", None)
    st.rerun()


def _render_usuarios(usuario_atual) -> None:
    db = SessionLocal()
    try:
        with st.expander("➕ Convidar / Cadastrar Novo Usuário", expanded=False):
            st.markdown("Insira o e-mail Google do colaborador e defina o perfil de acesso inicial.")
            with st.form("form_novo_usuario", clear_on_submit=True):
                novo_email = st.text_input("E-mail do Usuário (Google)")
                perfis_disponiveis = listar_perfis(db, usuario_atual)
                nomes_perfis_cad = [perfil.nome for perfil in perfis_disponiveis]
                
                novo_perfil_nome = st.selectbox("Perfil de Acesso (Role)", nomes_perfis_cad)
                
                submitted = st.form_submit_button("Cadastrar Usuário", use_container_width=True)
                if submitted:
                    if not novo_email or "@" not in novo_email:
                        st.error("Informe um e-mail válido.")
                    else:
                        try:
                            cadastrar_usuario(
                                db=db,
                                usuario_executor=usuario_atual,
                                email=novo_email.strip().lower(),
                                nome_perfil=novo_perfil_nome
                            )
                            st.success(f"Usuário {novo_email} cadastrado com sucesso!")
                            st.rerun()
                        except Exception as err:
                            db.rollback()
                            st.error(f"Erro ao cadastrar usuário: {err}")

        st.divider()

        # Listagem e Gestão dos usuários existentes
        usuarios = listar_usuarios(db, usuario_atual)
        perfis = listar_perfis(db, usuario_atual)

        render_dataframe_padrao(
            [
                {
                    "ID": usuario.id_usuario,
                    "Nome": usuario.nome or "Pendente de Primeiro Acesso",
                    "E-mail": usuario.email,
                    "Perfil": usuario.perfil.nome if usuario.perfil else "Sem Perfil",
                    "Ativo": usuario.ativo,
                    "Último login": usuario.ultimo_login_em,
                }
                for usuario in usuarios
            ]
        )

        if not usuarios:
            st.info("Nenhum usuário cadastrado.")
            return

        st.markdown("### Gerenciar Usuário Existente")
        opcoes = {f"{item.nome or 'Sem Nome'} · {item.email}": item for item in usuarios}
        rotulo_usuario = st.selectbox("Selecione o Usuário", list(opcoes))
        usuario_selecionado = opcoes[rotulo_usuario]
        
        nomes_perfis = [perfil.nome for perfil in perfis]
        indice_perfil = nomes_perfis.index(usuario_selecionado.perfil.nome) if usuario_selecionado.perfil and usuario_selecionado.perfil.nome in nomes_perfis else 0
        nome_perfil = st.selectbox("Novo Perfil", nomes_perfis, index=indice_perfil)

        col_perfil, col_status = st.columns(2)
        if col_perfil.button("Salvar perfil", use_container_width=True):
            alterar_perfil_usuario(
                db,
                usuario_atual,
                usuario_selecionado.id_usuario,
                nome_perfil,
            )
            st.success("Perfil atualizado.")
            if usuario_selecionado.id_usuario == usuario_atual.id_usuario:
                _recarregar_contexto_usuario()
            st.rerun()

        acao_status = "Desativar usuário" if usuario_selecionado.ativo else "Ativar usuário"
        if col_status.button(acao_status, use_container_width=True):
            alterar_status_usuario(
                db,
                usuario_atual,
                usuario_selecionado.id_usuario,
                not usuario_selecionado.ativo,
            )
            st.success("Situação do usuário atualizada.")
            st.rerun()
    except Exception as erro:
        db.rollback()
        st.error(f"Erro ao gerenciar usuários: {erro}")
    finally:
        db.close()


def _render_perfis_permissoes(usuario_atual) -> None:
    db = SessionLocal()
    try:
        perfis = listar_perfis(db, usuario_atual)
        permissoes = listar_permissoes(db, usuario_atual)
        codigos_permissoes = [permissao.codigo for permissao in permissoes]
        rotulos_permissoes = {
            permissao.codigo: f"{permissao.codigo} · {permissao.descricao}"
            for permissao in permissoes
        }

        st.markdown("### Perfis de acesso")
        st.caption(
            "Cada perfil combina as permissões usadas pelos módulos. "
            "Perfis padrão podem ter suas permissões alteradas, mas não podem ser renomeados ou excluídos."
        )
        st.dataframe(
            [
                {
                    "Perfil": perfil.nome,
                    "Descrição": perfil.descricao or "",
                    "Permissões": len(perfil.permissoes),
                    "Usuários": len(perfil.usuarios),
                    "Tipo": "Padrão" if perfil.nome in PERFIS_PADRAO else "Personalizado",
                }
                for perfil in perfis
            ],
            width="stretch",
            hide_index=True,
        )

        with st.expander("Criar novo perfil", expanded=False):
            with st.form("form_criar_perfil", clear_on_submit=True):
                novo_nome = st.text_input("Nome do perfil")
                nova_descricao = st.text_input("Descrição")
                novas_permissoes = st.multiselect(
                    "Permissões iniciais",
                    codigos_permissoes,
                    format_func=lambda codigo: rotulos_permissoes[codigo],
                )
                if st.form_submit_button("Criar perfil", use_container_width=True):
                    try:
                        criar_perfil(
                            db,
                            usuario_atual,
                            novo_nome,
                            nova_descricao,
                            novas_permissoes,
                        )
                        st.success("Perfil criado.")
                        st.rerun()
                    except Exception as erro:
                        db.rollback()
                        st.error(f"Erro ao criar perfil: {erro}")

        if perfis:
            opcoes_perfis = {perfil.nome: perfil for perfil in perfis}
            nome_selecionado = st.selectbox(
                "Perfil para editar",
                list(opcoes_perfis),
                key="perfil_dinamico_selecionado",
            )
            perfil_selecionado = opcoes_perfis[nome_selecionado]
            perfil_padrao = perfil_selecionado.nome in PERFIS_PADRAO
            permissoes_atuais = [
                permissao.codigo for permissao in perfil_selecionado.permissoes
            ]

            with st.form(f"form_editar_perfil_{perfil_selecionado.id_perfil}"):
                nome_editado = st.text_input(
                    "Nome",
                    value=perfil_selecionado.nome,
                    disabled=perfil_padrao,
                )
                descricao_editada = st.text_input(
                    "Descrição",
                    value=perfil_selecionado.descricao or "",
                )
                permissoes_editadas = st.multiselect(
                    "Permissões do perfil",
                    codigos_permissoes,
                    default=permissoes_atuais,
                    format_func=lambda codigo: rotulos_permissoes[codigo],
                )
                if st.form_submit_button("Salvar alterações", use_container_width=True):
                    try:
                        perfil_do_usuario_atual = perfil_selecionado.nome == usuario_atual.perfil
                        atualizar_perfil(
                            db,
                            usuario_atual,
                            perfil_selecionado.id_perfil,
                            perfil_selecionado.nome if perfil_padrao else nome_editado,
                            descricao_editada,
                            permissoes_editadas,
                        )
                        st.success("Perfil e permissões atualizados.")
                        if perfil_do_usuario_atual:
                            _recarregar_contexto_usuario()
                        st.rerun()
                    except Exception as erro:
                        db.rollback()
                        st.error(f"Erro ao atualizar perfil: {erro}")

            confirmar_exclusao = st.checkbox(
                "Confirmo a exclusão deste perfil",
                key=f"confirmar_exclusao_perfil_{perfil_selecionado.id_perfil}",
                disabled=perfil_padrao,
            )
            if st.button(
                "Excluir perfil",
                key=f"excluir_perfil_{perfil_selecionado.id_perfil}",
                disabled=perfil_padrao or not confirmar_exclusao,
            ):
                try:
                    excluir_perfil(db, usuario_atual, perfil_selecionado.id_perfil)
                    st.success("Perfil excluído.")
                    st.rerun()
                except Exception as erro:
                    db.rollback()
                    st.error(f"Erro ao excluir perfil: {erro}")

        st.divider()
        st.markdown("### Catálogo de permissões")
        st.caption(
            "O código identifica a permissão no sistema e não pode ser renomeado. "
            "Permissões personalizadas passam a ter efeito quando forem usadas por um módulo."
        )
        st.dataframe(
            [
                {
                    "Código": permissao.codigo,
                    "Descrição": permissao.descricao,
                    "Perfis vinculados": len(permissao.perfis),
                    "Tipo": "Sistema" if permissao.codigo in PERMISSOES_PADRAO else "Personalizada",
                }
                for permissao in permissoes
            ],
            width="stretch",
            hide_index=True,
        )

        with st.expander("Criar nova permissão", expanded=False):
            with st.form("form_criar_permissao", clear_on_submit=True):
                novo_codigo = st.text_input(
                    "Código",
                    placeholder="exemplo: relatorios.exportar",
                )
                descricao_permissao = st.text_input("Descrição da permissão")
                if st.form_submit_button("Criar permissão", use_container_width=True):
                    try:
                        criar_permissao(
                            db,
                            usuario_atual,
                            novo_codigo,
                            descricao_permissao,
                        )
                        st.success("Permissão criada.")
                        st.rerun()
                    except Exception as erro:
                        db.rollback()
                        st.error(f"Erro ao criar permissão: {erro}")

        if permissoes:
            opcoes = {permissao.codigo: permissao for permissao in permissoes}
            codigo_selecionado = st.selectbox(
                "Permissão para editar",
                list(opcoes),
                key="permissao_dinamica_selecionada",
            )
            permissao_selecionada = opcoes[codigo_selecionado]
            permissao_sistema = permissao_selecionada.codigo in PERMISSOES_PADRAO
            with st.form(
                f"form_editar_permissao_{permissao_selecionada.id_permissao}"
            ):
                st.text_input("Código", value=permissao_selecionada.codigo, disabled=True)
                descricao_editada = st.text_input(
                    "Descrição",
                    value=permissao_selecionada.descricao,
                    key=f"descricao_permissao_{permissao_selecionada.id_permissao}",
                )
                if st.form_submit_button("Salvar descrição", use_container_width=True):
                    try:
                        atualizar_permissao(
                            db,
                            usuario_atual,
                            permissao_selecionada.id_permissao,
                            descricao_editada,
                        )
                        st.success("Permissão atualizada.")
                        st.rerun()
                    except Exception as erro:
                        db.rollback()
                        st.error(f"Erro ao atualizar permissão: {erro}")

            confirmar_exclusao = st.checkbox(
                "Confirmo a exclusão desta permissão",
                key=f"confirmar_exclusao_permissao_{permissao_selecionada.id_permissao}",
                disabled=permissao_sistema,
            )
            if st.button(
                "Excluir permissão",
                key=f"excluir_permissao_{permissao_selecionada.id_permissao}",
                disabled=permissao_sistema or not confirmar_exclusao,
            ):
                try:
                    excluir_permissao(
                        db,
                        usuario_atual,
                        permissao_selecionada.id_permissao,
                    )
                    st.success("Permissão excluída.")
                    st.rerun()
                except Exception as erro:
                    db.rollback()
                    st.error(f"Erro ao excluir permissão: {erro}")
    except Exception as erro:
        db.rollback()
        st.error(f"Erro ao gerenciar perfis e permissões: {erro}")
    finally:
        db.close()


def _render_auditoria(usuario_atual) -> None:
    db = SessionLocal()
    try:
        logs = listar_logs(db, usuario_atual, limite=200)
        st.caption("Últimas 200 operações registradas")
        render_dataframe_padrao(
            [
                {
                    "Data/hora": log.data_hora,
                    "Usuário": log.usuario.email if log.usuario else "Sistema",
                    "Módulo": log.modulo,
                    "Ação": log.acao,
                    "Entidade": log.entidade,
                    "Registro": log.id_registro,
                    "Detalhes": log.detalhes,
                }
                for log in logs
            ]
        )
    except Exception as erro:
        st.error(f"Erro ao consultar auditoria: {erro}")
    finally:
        db.close()


def render_admin(usuario_atual) -> None:
    render_cabecalho(
        "Administração",
        "Gerencie usuários, perfis de acesso e consulte operações auditadas.",
    )
    nomes_abas = []
    if usuario_atual.pode("usuarios.gerenciar"):
        nomes_abas.extend(["Usuários", "Perfis e permissões"])
    if usuario_atual.pode("auditoria.visualizar"):
        nomes_abas.append("Auditoria")

    if not nomes_abas:
        st.warning("Você não tem permissão para visualizar esta página.")
        return

    abas = st.tabs(nomes_abas)
    for nome, aba in zip(nomes_abas, abas):
        with aba:
            if nome == "Usuários":
                _render_usuarios(usuario_atual)
            elif nome == "Perfis e permissões":
                _render_perfis_permissoes(usuario_atual)
            else:
                _render_auditoria(usuario_atual)
