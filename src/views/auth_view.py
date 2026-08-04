from html import escape

import streamlit as st

from config.settings import ADMIN_EMAILS
from src.database.connection import SessionLocal
from src.services.auth_service import criar_contexto_usuario, sincronizar_usuario_google


def _auth_google_configurada() -> bool:
    try:
        auth = st.secrets.get("auth", {})
        campos = ("redirect_uri", "cookie_secret", "client_id", "client_secret")
        return all(auth.get(campo) for campo in campos)
    except (FileNotFoundError, KeyError, TypeError):
        return False


def exigir_login_google():
    if not _auth_google_configurada():
        st.error("O login Google ainda não foi configurado.")
        st.info(
            "Copie `.streamlit/secrets.toml.example` para "
            "`.streamlit/secrets.toml` e informe as credenciais OIDC do Google."
        )
        st.stop()

    if not getattr(st.user, "is_logged_in", False):
        st.markdown("## Acesso ao FioNobre ERP")
        st.write("Entre com sua conta Google para acessar o sistema.")
        st.button("Entrar com Google", on_click=st.login, type="primary")
        st.stop()

    if "usuario_contexto" not in st.session_state:
        db = SessionLocal()
        try:
            usuario = sincronizar_usuario_google(
                db,
                st.user.to_dict(),
                admin_emails=ADMIN_EMAILS,
            )
            st.session_state["usuario_contexto"] = criar_contexto_usuario(usuario)
        except Exception as erro:
            db.rollback()
            st.error(f"Não foi possível autorizar o usuário: {erro}")
            st.button("Sair", on_click=st.logout)
            st.stop()
        finally:
            db.close()

    return st.session_state["usuario_contexto"]


def render_usuario_topbar(usuario) -> None:
    nome = escape(usuario.nome)
    email = escape(usuario.email)
    perfil = escape(usuario.perfil)
    primeiro_nome = usuario.nome.split()[0] if usuario.nome.split() else "Conta"
    _, coluna_conta = st.columns([5.8, 1.55], vertical_alignment="center")
    with coluna_conta:
        with st.container(key="account_menu"):
            coluna_foto, coluna_menu = st.columns(
                [0.3, 1.35], gap=None, vertical_alignment="center"
            )
            with coluna_foto:
                if usuario.foto_url and usuario.foto_url.startswith("https://"):
                    st.markdown(
                        f'<img class="fn-account-static-avatar" '
                        f'src="{escape(usuario.foto_url)}" alt="Foto de {nome}">',
                        unsafe_allow_html=True,
                    )
                else:
                    iniciais = "".join(
                        parte[0] for parte in usuario.nome.split()[:2]
                    ).upper() or "FN"
                    st.markdown(
                        f'<div class="fn-account-initials">{escape(iniciais)}</div>',
                        unsafe_allow_html=True,
                    )
            with coluna_menu:
                with st.popover(primeiro_nome, use_container_width=True):
                    st.markdown(
                        f"""
                        <div class="fn-account-menu">
                            <div class="fn-account-menu-name">{nome}</div>
                            <div class="fn-account-menu-email">{email}</div>
                            <div class="fn-profile-role">{perfil}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.button(
                        "Sair da conta",
                        on_click=st.logout,
                        use_container_width=True,
                        key="logout_topbar",
                    )
