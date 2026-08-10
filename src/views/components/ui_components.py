import streamlit as st
import pandas as pd


def aplicar_estilo_global():
    """Aplica estilos CSS customizados para refinar o layout em tons pastéis."""
    st.markdown("""
        <style>
        /* Ajuste fino dos cards e métricas */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #D9E2EC;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        /* Estilização de botões principais */
        .stButton>button {
            background-color: #2E7D32;
            color: white;
            border-radius: 6px;
            border: none;
            font-weight: 500;
        }
        .stButton>button:hover {
            background-color: #1B5E20;
            color: white;
        }
        </style>
    """, unsafe_allow_html=True)


def render_cabecalho(titulo: str, subtitulo: str):
    """Componente reutilizável para cabeçalho das páginas."""
    st.markdown(f"## 🌿 {titulo}")
    st.markdown(f"<p style='color: #557A95; font-size: 1.1rem;'>{subtitulo}</p>", unsafe_allow_html=True)
    st.markdown("---")


def render_dataframe_padrao(dados, altura=None):
    """Exibe DataFrame/lista no padrão visual único do ERP."""
    if isinstance(dados, list):
        if not dados:
            st.info("Nenhum registro para exibir.")
            return
        dados = pd.DataFrame(dados)

    kwargs = {
        "use_container_width": True,
        "hide_index": True,
    }
    if altura is not None:
        kwargs["height"] = altura
    st.dataframe(dados, **kwargs)


def render_cabecalho_tabela(rotulos: list[str], pesos: list[float]):
    """Cabeçalho padronizado para tabelas com ações por linha."""
    cols = st.columns(pesos)
    for col, rotulo in zip(cols, rotulos):
        col.write(f"**{rotulo}**")
    st.markdown("---")
    return pesos


def render_filtros_periodo_status(
    opcoes_status: list[str],
    chave_prefixo: str,
    dias_padrao: int = 90,
    incluir_busca: bool = True,
    placeholder_busca: str = "Buscar por ID, cliente ou documento...",
):
    """
    Bloco padrão de filtros: busca textual, status e intervalo de datas.
    Retorna (busca, status_ou_None, data_inicio, data_fim).
    """
    from datetime import datetime, timedelta

    st.subheader("Filtros")

    if incluir_busca:
        busca = st.text_input(
            "Busca",
            value="",
            placeholder=placeholder_busca,
            key=f"{chave_prefixo}_busca",
        )
    else:
        busca = ""

    col_status, col_dt_ini, col_dt_fim = st.columns(3)
    with col_status:
        filtro_status = st.selectbox(
            "Status",
            options=opcoes_status,
            key=f"{chave_prefixo}_status",
        )
    with col_dt_ini:
        data_inicio = st.date_input(
            "Data Inicial",
            value=datetime.now() - timedelta(days=dias_padrao),
            key=f"{chave_prefixo}_dt_ini",
        )
    with col_dt_fim:
        data_fim = st.date_input(
            "Data Final",
            value=datetime.now(),
            key=f"{chave_prefixo}_dt_fim",
        )

    status_param = None if filtro_status in ("Todos", "Todas") else filtro_status
    return busca.strip(), status_param, data_inicio, data_fim
