import streamlit as st

from src.database.connection import SessionLocal
from src.database.models.usuarios import Perfil
from src.services.usuario_service import (
    alterar_perfil_usuario,
    alterar_status_usuario,
    listar_logs,
    listar_usuarios,
    cadastrar_usuario, 
)
from src.views.components.ui_components import render_cabecalho


def _render_usuarios(usuario_atual) -> None:
    db = SessionLocal()
    try:
        with st.expander("➕ Convidar / Cadastrar Novo Usuário", expanded=False):
            st.markdown("Insira o e-mail Google do colaborador e defina o perfil de acesso inicial.")
            with st.form("form_novo_usuario", clear_on_submit=True):
                novo_email = st.text_input("E-mail do Usuário (Google)")
                perfis_disponiveis = db.query(Perfil).order_by(Perfil.nome).all()
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
        perfis = db.query(Perfil).order_by(Perfil.nome).all()

        st.dataframe(
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
            ],
            width="stretch",
            hide_index=True,
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


def _render_auditoria(usuario_atual) -> None:
    db = SessionLocal()
    try:
        logs = listar_logs(db, usuario_atual, limite=200)
        st.caption("Últimas 200 operações registradas")
        st.dataframe(
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
            ],
            width="stretch",
            hide_index=True,
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
        nomes_abas.append("Usuários")
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
            else:
                _render_auditoria(usuario_atual)