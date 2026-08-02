import streamlit as st

from src.database.connection import SessionLocal
from src.database.models.usuarios import Perfil
from src.services.usuario_service import (
    alterar_perfil_usuario,
    alterar_status_usuario,
    listar_logs,
    listar_usuarios,
)
from src.views.components.ui_components import render_cabecalho


def _render_usuarios(usuario_atual) -> None:
    db = SessionLocal()
    try:
        usuarios = listar_usuarios(db, usuario_atual)
        perfis = db.query(Perfil).order_by(Perfil.nome).all()

        st.dataframe(
            [
                {
                    "ID": usuario.id_usuario,
                    "Nome": usuario.nome,
                    "E-mail": usuario.email,
                    "Perfil": usuario.perfil.nome,
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

        opcoes = {f"{item.nome} · {item.email}": item for item in usuarios}
        rotulo_usuario = st.selectbox("Usuário", list(opcoes))
        usuario_selecionado = opcoes[rotulo_usuario]
        nomes_perfis = [perfil.nome for perfil in perfis]
        indice_perfil = nomes_perfis.index(usuario_selecionado.perfil.nome)
        nome_perfil = st.selectbox("Perfil", nomes_perfis, index=indice_perfil)

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
                    "Usuário": log.usuario.email,
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

    abas = st.tabs(nomes_abas)
    for nome, aba in zip(nomes_abas, abas):
        with aba:
            if nome == "Usuários":
                _render_usuarios(usuario_atual)
            else:
                _render_auditoria(usuario_atual)
