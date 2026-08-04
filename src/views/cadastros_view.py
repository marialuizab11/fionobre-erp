import streamlit as st

from src.database.connection import SessionLocal
from src.database.models.cadastros import Cliente, Item
from src.services.cadastro_service import criar_cliente, criar_item
from src.views.components.ui_components import render_cabecalho


def _render_clientes(db, usuario_atual) -> None:
    with st.form("cadastro_cliente", clear_on_submit=True):
        st.markdown("### Novo cliente")
        razao_social = st.text_input("Nome/Razão social *")
        cnpj_cpf = st.text_input("CPF/CNPJ *")
        col1, col2 = st.columns(2)
        email = col1.text_input("E-mail")
        telefone = col2.text_input("Telefone")
        col3, col4, col5 = st.columns([2, 3, 1])
        cep = col3.text_input("CEP")
        rua = col4.text_input("Rua")
        numero = col5.text_input("Número")
        col6, col7, col8 = st.columns([2, 2, 1])
        bairro = col6.text_input("Bairro")
        cidade = col7.text_input("Cidade")
        uf = col8.text_input("UF", max_chars=2)
        enviado = st.form_submit_button("Cadastrar cliente", type="primary")

    if enviado:
        try:
            criar_cliente(
                db,
                usuario_atual,
                razao_social,
                cnpj_cpf,
                email=email,
                telefone=telefone,
                cep=cep,
                rua=rua,
                numero=numero,
                bairro=bairro,
                cidade=cidade,
                uf=uf,
            )
            st.success("Cliente cadastrado com sucesso.")
        except Exception as erro:
            st.error(str(erro))

    clientes = db.query(Cliente).order_by(Cliente.razao_social).all()
    st.markdown("### Clientes cadastrados")
    st.dataframe(
        [
            {
                "ID": cliente.id_cliente,
                "Nome/Razão social": cliente.razao_social,
                "CPF/CNPJ": cliente.cnpj_cpf,
                "E-mail": cliente.email,
                "Telefone": cliente.telefone,
                "Cidade": cliente.cidade,
                "UF": cliente.uf,
            }
            for cliente in clientes
        ],
        width="stretch",
        hide_index=True,
    )


def _render_itens(db, usuario_atual) -> None:
    with st.form("cadastro_item", clear_on_submit=True):
        st.markdown("### Novo item")
        descricao = st.text_input("Descrição *")
        col1, col2 = st.columns(2)
        tipo_item = col1.selectbox(
            "Tipo *",
            ["PRODUTO_ACABADO", "MATERIA_PRIMA", "INSUMO"],
        )
        unidade = col2.selectbox("Unidade *", ["UN", "KG", "M", "L", "CX"])
        col3, col4 = st.columns(2)
        saldo = col3.number_input("Saldo inicial", min_value=0.0, step=1.0)
        minimo = col4.number_input("Estoque mínimo", min_value=0.0, step=1.0)
        col5, col6 = st.columns(2)
        preco = col5.number_input("Preço de venda (R$)", min_value=0.0, step=0.01)
        custo = col6.number_input("Custo médio (R$)", min_value=0.0, step=0.01)
        enviado = st.form_submit_button("Cadastrar item", type="primary")

    if enviado:
        try:
            criar_item(
                db,
                usuario_atual,
                descricao,
                unidade,
                tipo_item,
                saldo_inicial=saldo,
                estoque_minimo=minimo,
                preco_venda=preco,
                custo_medio=custo,
            )
            st.success("Item cadastrado com sucesso.")
        except Exception as erro:
            st.error(str(erro))

    itens = db.query(Item).order_by(Item.descricao).all()
    st.markdown("### Itens cadastrados")
    st.dataframe(
        [
            {
                "ID": item.id_item,
                "Descrição": item.descricao,
                "Tipo": item.tipo_item,
                "Unidade": item.unidade_medida,
                "Saldo": float(item.saldo_estoque),
                "Mínimo": float(item.estoque_minimo),
                "Preço (R$)": float(item.preco_venda),
                "Custo (R$)": float(item.custo_medio),
            }
            for item in itens
        ],
        width="stretch",
        hide_index=True,
    )


def render_cadastros(usuario_atual) -> None:
    render_cabecalho(
        "Cadastros",
        "Cadastre clientes, matérias-primas, insumos e produtos acabados.",
    )
    db = SessionLocal()
    try:
        aba_clientes, aba_itens = st.tabs(["Clientes", "Itens"])
        with aba_clientes:
            _render_clientes(db, usuario_atual)
        with aba_itens:
            _render_itens(db, usuario_atual)
    finally:
        db.close()
