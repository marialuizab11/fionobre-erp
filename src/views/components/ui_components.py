import streamlit as st


def aplicar_estilo_global():
    """Aplica a identidade visual do FioNobre ERP."""
    st.markdown(
        """
        <style>
        :root {
            --fn-green: #1f6b45;
            --fn-green-dark: #164c33;
            --fn-green-soft: #e7f2eb;
            --fn-ink: #1f2d26;
            --fn-muted: #6f7f76;
            --fn-line: #dce5df;
            --fn-sidebar: #f7faf8;
        }

        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid var(--fn-line);
            padding: 15px;
            border-radius: 12px;
            box-shadow: 0 5px 18px rgba(31, 45, 38, 0.05);
        }

        .stButton > button {
            background: var(--fn-green);
            color: white;
            border: 0;
            border-radius: 9px;
            font-weight: 600;
            min-height: 2.6rem;
            transition: background 160ms ease, transform 160ms ease;
        }
        .stButton > button:hover {
            background: var(--fn-green-dark);
            color: white;
            transform: translateY(-1px);
        }

        section[data-testid="stSidebar"] {
            background: var(--fn-sidebar);
            border-right: 1px solid var(--fn-line);
        }
        section[data-testid="stSidebar"] > div {
            padding-top: 0.8rem;
        }
        section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.45rem;
        }

        .fn-brand {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            padding: 0.35rem 0.15rem 1rem;
            margin-bottom: 0.35rem;
            border-bottom: 1px solid var(--fn-line);
        }
        .fn-brand-mark {
            width: 44px;
            height: 44px;
            display: grid;
            place-items: center;
            border-radius: 13px;
            color: #ffffff;
            background: linear-gradient(145deg, #2f8a5d, #18583a);
            box-shadow: 0 6px 14px rgba(31, 107, 69, 0.22);
            font-size: 1.25rem;
        }
        .fn-brand-name {
            color: var(--fn-ink);
            font-size: 1.2rem;
            font-weight: 750;
            line-height: 1.1;
            letter-spacing: -0.02em;
        }
        .fn-brand-subtitle {
            color: var(--fn-muted);
            font-size: 0.66rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            margin-top: 0.25rem;
        }
        .fn-section-label {
            color: #849188;
            font-size: 0.66rem;
            font-weight: 750;
            letter-spacing: 0.12em;
            padding: 0.55rem 0.65rem 0.25rem;
        }

        section[data-testid="stSidebar"] div[data-testid="stRadio"] > label {
            display: none;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] {
            gap: 0.22rem;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label {
            width: 100%;
            min-height: 2.55rem;
            padding: 0.58rem 0.72rem;
            border: 1px solid transparent;
            border-radius: 9px;
            color: #435149;
            background: transparent;
            transition: all 150ms ease;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
            color: var(--fn-green-dark);
            background: #edf4ef;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
            color: var(--fn-green-dark);
            background: var(--fn-green-soft);
            border-color: #cfe3d6;
            font-weight: 700;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {
            display: none;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] p {
            font-size: 0.9rem;
        }

        .fn-profile {
            margin-top: 0.7rem;
            padding: 0.85rem;
            border: 1px solid var(--fn-line);
            border-radius: 12px;
            background: #ffffff;
            box-shadow: 0 5px 16px rgba(31, 45, 38, 0.04);
        }
        .st-key-account_menu {
            min-height: 2.8rem;
        }
        .fn-account-initials {
            display: grid;
            place-items: center;
            width: 40px;
            height: 40px;
            color: #ffffff;
            background: var(--fn-green);
            border-radius: 10px;
            font-size: 0.75rem;
            font-weight: 750;
        }
        .fn-account-static-avatar {
            display: block;
            width: 40px;
            height: 40px;
            border-radius: 10px;
            object-fit: cover;
        }
        .st-key-account_menu div[data-testid="stPopover"] > button {
            width: 100%;
            min-height: 2.55rem;
            color: var(--fn-ink);
            background: #ffffff;
            border: 1px solid var(--fn-line);
            border-radius: 10px;
            box-shadow: 0 3px 12px rgba(31, 45, 38, 0.05);
            font-weight: 700;
            padding-left: 0.55rem;
        }
        .st-key-account_menu div[data-testid="stPopover"] > button:hover,
        .st-key-account_menu div[data-testid="stPopover"] > button:focus {
            color: var(--fn-green-dark);
            background: var(--fn-green-soft);
            border-color: #cfe3d6;
        }
        .fn-account-menu {
            min-width: 230px;
            padding: 0.25rem 0.15rem 0.7rem;
        }
        .fn-account-menu-name {
            color: var(--fn-ink);
            font-size: 0.92rem;
            font-weight: 750;
        }
        .fn-account-menu-email {
            color: var(--fn-muted);
            font-size: 0.75rem;
            margin-top: 0.18rem;
        }
        .fn-profile-head {
            display: flex;
            align-items: center;
            gap: 0.7rem;
        }
        .fn-profile-avatar,
        .fn-profile-initials {
            width: 42px;
            height: 42px;
            flex: 0 0 42px;
            border-radius: 11px;
        }
        .fn-profile-avatar { object-fit: cover; }
        .fn-profile-initials {
            display: grid;
            place-items: center;
            color: #ffffff;
            background: var(--fn-green);
            font-weight: 750;
        }
        .fn-profile-name {
            color: var(--fn-ink);
            font-size: 0.88rem;
            font-weight: 700;
            line-height: 1.2;
        }
        .fn-profile-email {
            max-width: 150px;
            overflow: hidden;
            color: var(--fn-muted);
            font-size: 0.72rem;
            text-overflow: ellipsis;
            white-space: nowrap;
            margin-top: 0.18rem;
        }
        .fn-profile-role {
            display: inline-block;
            color: var(--fn-green-dark);
            background: var(--fn-green-soft);
            border-radius: 99px;
            padding: 0.2rem 0.5rem;
            margin-top: 0.65rem;
            font-size: 0.67rem;
            font-weight: 700;
        }
        .fn-version {
            color: #96a198;
            font-size: 0.65rem;
            text-align: center;
            padding-top: 0.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_marca_sidebar() -> None:
    st.sidebar.markdown(
        """
        <div class="fn-brand">
            <div class="fn-brand-mark">🧵</div>
            <div>
                <div class="fn-brand-name">FioNobre</div>
                <div class="fn-brand-subtitle">ERP INDUSTRIAL</div>
            </div>
        </div>
        <div class="fn-section-label">NAVEGAÇÃO</div>
        """,
        unsafe_allow_html=True,
    )


def render_cabecalho(titulo: str, subtitulo: str):
    """Componente reutilizável para cabeçalho das páginas."""
    st.markdown(f"## 🌿 {titulo}")
    st.markdown(
        f"<p style='color:#62746a;font-size:1.05rem'>{subtitulo}</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
