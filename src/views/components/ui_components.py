import streamlit as st

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