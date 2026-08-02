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


def render_usuario_sidebar(usuario) -> None:
    st.sidebar.markdown("### Usuário")
    if usuario.foto_url:
        st.sidebar.image(usuario.foto_url, width=64)
    st.sidebar.write(usuario.nome)
    st.sidebar.caption(f"{usuario.email} · {usuario.perfil}")
    st.sidebar.button("Sair", on_click=st.logout, use_container_width=True)
