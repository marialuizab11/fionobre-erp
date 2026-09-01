import traceback
import streamlit as st
import pandas as pd

from src.database.connection import SessionLocal
from src.services.cadastro_service import (
    criar_cliente,
    editar_cliente,
    remover_cliente,
    listar_clientes,
    criar_item,
    editar_item,
    remover_item,
    listar_itens,
    criar_fornecedor,
    editar_fornecedor,
    remover_fornecedor,
    listar_fornecedores,
)
from src.views.components.ui_components import render_cabecalho


# ==========================================
# DIÁLOGOS DE CLIENTE (EDIÇÃO E EXCLUSÃO)
# ==========================================

@st.dialog("Editar Cliente")
def modal_editar_cliente(cliente, usuario_atual):
    with st.form("form_editar_cliente"):
        razao_social = st.text_input("Nome/Razão social *", value=cliente.razao_social)
        cnpj_cpf = st.text_input("CPF/CNPJ *", value=cliente.cnpj_cpf)
        col1, col2 = st.columns(2)
        email = col1.text_input("E-mail", value=cliente.email or "")
        telefone = col2.text_input("Telefone", value=cliente.telefone or "")
        col3, col4, col5 = st.columns([2, 3, 1])
        cep = col3.text_input("CEP", value=cliente.cep or "")
        rua = col4.text_input("Rua", value=cliente.rua or "")
        numero = col5.text_input("Número", value=cliente.numero or "")
        col6, col7, col8 = st.columns([2, 2, 1])
        bairro = col6.text_input("Bairro", value=cliente.bairro or "")
        cidade = col7.text_input("Cidade", value=cliente.cidade or "")
        uf = col8.text_input("UF", value=cliente.uf or "", max_chars=2)

        submitted = st.form_submit_button("Salvar Alterações", type="primary", use_container_width=True)

    if submitted:
        db = SessionLocal()
        try:
            editar_cliente(
                db,
                usuario_atual,
                cliente.id_cliente,
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
            st.toast("Cliente atualizado com sucesso!", icon="✅")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao atualizar: {e}")
        finally:
            db.close()


@st.dialog("Excluir Cliente")
def modal_excluir_cliente(cliente, usuario_atual):
    st.warning(f"Tem certeza que deseja excluir o cliente **{cliente.razao_social}** ({cliente.cnpj_cpf})?")
    st.caption("Esta ação não poderá ser desfeita e falhará caso o cliente tenha vendas vinculadas.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirmar Exclusão", type="primary", use_container_width=True):
            db = SessionLocal()
            try:
                remover_cliente(db, usuario_atual, cliente.id_cliente)
                st.toast("Cliente removido com sucesso!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(str(e))
            finally:
                db.close()
    with col2:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()


def _render_clientes(db, usuario_atual) -> None:
    with st.expander("➕ Novo Cliente", expanded=False):
        with st.form("cadastro_cliente", clear_on_submit=True):
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
            enviado = st.form_submit_button("Cadastrar cliente", type="primary", use_container_width=True)

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
                st.rerun()
            except Exception as erro:
                st.error(str(erro))

    clientes = listar_clientes(db)
    st.markdown("### Clientes Cadastrados")
    
    if not clientes:
        st.info("Nenhum cliente cadastrado.")
        return

    dados_clientes = []
    for cli in clientes:
        dados_clientes.append({
            "ID": cli.id_cliente,
            "Nome/Razão Social": cli.razao_social,
            "CPF/CNPJ": cli.cnpj_cpf,
            "E-mail": cli.email or "-",
            "Cidade/UF": f"{cli.cidade or '-'}/{cli.uf or '-'}"
        })
    df_clientes = pd.DataFrame(dados_clientes)
    st.dataframe(df_clientes, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.write("#### Ações do Cliente")
    col_id, col_ed, col_del, _ = st.columns([3, 2, 2, 3])
    
    with col_id:
        cli_opcoes = {c.id_cliente: f"ID {c.id_cliente} - {c.razao_social}" for c in clientes}
        cli_selecionado_id = st.selectbox("Selecione o Cliente:", options=list(cli_opcoes.keys()), format_func=lambda x: cli_opcoes[x], key="sel_cli")
    
    cli_obj = next((c for c in clientes if c.id_cliente == cli_selecionado_id), None)
    
    with col_ed:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Editar", key="ed_cli_btn", use_container_width=True):
            modal_editar_cliente(cli_obj, usuario_atual)
            
    with col_del:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Excluir", key="del_cli_btn", use_container_width=True):
            modal_excluir_cliente(cli_obj, usuario_atual)


# ==========================================
# DIÁLOGOS DE ITEM (EDIÇÃO E EXCLUSÃO)
# ==========================================

@st.dialog("Editar Item")
def modal_editar_item(item, usuario_atual):
    with st.form("form_editar_item"):
        descricao = st.text_input("Descrição *", value=item.descricao)
        col1, col2 = st.columns(2)
        tipos = ["PRODUTO_ACABADO", "MATERIA_PRIMA", "INSUMO"]
        idx_tipo = tipos.index(item.tipo_item) if item.tipo_item in tipos else 0
        tipo_item = col1.selectbox("Tipo *", tipos, index=idx_tipo)
        
        unidades = ["UN", "KG", "M", "L", "CX"]
        idx_uni = unidades.index(item.unidade_medida) if item.unidade_medida in unidades else 0
        unidade = col2.selectbox("Unidade *", unidades, index=idx_uni)

        col3, col4 = st.columns(2)
        minimo = col3.number_input("Estoque mínimo", min_value=0.0, step=1.0, value=float(item.estoque_minimo))
        preco = col4.number_input("Preço de venda (R$)", min_value=0.0, step=0.01, value=float(item.preco_venda))
        custo = st.number_input("Custo médio (R$)", min_value=0.0, step=0.01, value=float(item.custo_medio))

        submitted = st.form_submit_button("Salvar Alterações", type="primary", use_container_width=True)

    if submitted:
        db = SessionLocal()
        try:
            editar_item(
                db,
                usuario_atual,
                item.id_item,
                descricao,
                unidade,
                tipo_item,
                estoque_minimo=minimo,
                preco_venda=preco,
                custo_medio=custo,
            )
            st.toast("Item atualizado com sucesso!", icon="✅")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao atualizar: {e}")
        finally:
            db.close()


@st.dialog("Excluir Item")
def modal_excluir_item(item, usuario_atual):
    st.warning(f"Tem certeza que deseja excluir o item **{item.descricao}**?")
    st.caption("Esta ação não poderá ser desfeita e falhará caso o item possua movimentações de estoque ou vendas associadas.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirmar Exclusão", type="primary", use_container_width=True):
            db = SessionLocal()
            try:
                remover_item(db, usuario_atual, item.id_item)
                st.toast("Item removido com sucesso!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(str(e))
            finally:
                db.close()
    with col2:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()


def _render_itens(db, usuario_atual) -> None:
    with st.expander("➕ Novo Item", expanded=False):
        with st.form("cadastro_item", clear_on_submit=True):
            descricao = st.text_input("Descrição *")
            col1, col2 = st.columns(2)
            tipo_item = col1.selectbox("Tipo *", ["PRODUTO_ACABADO", "MATERIA_PRIMA", "INSUMO"])
            unidade = col2.selectbox("Unidade *", ["UN", "KG", "M", "L", "CX"])
            col3, col4 = st.columns(2)
            saldo = col3.number_input("Saldo inicial", min_value=0.0, step=1.0)
            minimo = col4.number_input("Estoque mínimo", min_value=0.0, step=1.0)
            col5, col6 = st.columns(2)
            preco = col5.number_input("Preço de venda (R$)", min_value=0.0, step=0.01)
            custo = col6.number_input("Custo médio (R$)", min_value=0.0, step=0.01)
            enviado = st.form_submit_button("Cadastrar item", type="primary", use_container_width=True)

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
                st.rerun()
            except Exception as erro:
                st.error(str(erro))

    itens = listar_itens(db)
    st.markdown("### Itens Cadastrados")

    if not itens:
        st.info("Nenhum item cadastrado.")
        return

    dados_itens = []
    for item in itens:
        dados_itens.append({
            "ID": item.id_item,
            "Descrição": item.descricao,
            "Tipo": item.tipo_item,
            "Saldo": f"{float(item.saldo_estoque):.2f} {item.unidade_medida}",
            "Preço (R$)": f"{float(item.preco_venda):.2f}",
            "Custo (R$)": f"{float(item.custo_medio):.2f}"
        })
    df_itens = pd.DataFrame(dados_itens)
    st.dataframe(df_itens, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.write("#### Ações do Item")
    col_id, col_ed, col_del, _ = st.columns([3, 2, 2, 3])
    
    with col_id:
        item_opcoes = {i.id_item: f"ID {i.id_item} - {i.descricao}" for i in itens}
        item_selecionado_id = st.selectbox("Selecione o Item:", options=list(item_opcoes.keys()), format_func=lambda x: item_opcoes[x], key="sel_item")
    
    item_obj = next((i for i in itens if i.id_item == item_selecionado_id), None)
    
    with col_ed:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Editar", key="ed_item_btn", use_container_width=True):
            modal_editar_item(item_obj, usuario_atual)
            
    with col_del:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Excluir", key="del_item_btn", use_container_width=True):
            modal_excluir_item(item_obj, usuario_atual)


# ==========================================
# DIÁLOGOS DE FORNECEDOR (EDIÇÃO E EXCLUSÃO)
# ==========================================

@st.dialog("Editar Fornecedor")
def modal_editar_fornecedor(fornecedor, usuario_atual):
    doc_atual = getattr(fornecedor, 'cnpj', getattr(fornecedor, 'cnpj_cpf', ''))
    with st.form("form_editar_fornecedor"):
        razao_social = st.text_input("Razão Social *", value=fornecedor.razao_social)
        cnpj = st.text_input("CNPJ / CPF *", value=doc_atual)
        col1, col2 = st.columns(2)
        email = col1.text_input("E-mail", value=fornecedor.email or "")
        telefone = col2.text_input("Telefone", value=fornecedor.telefone or "")

        submitted = st.form_submit_button("Salvar Alterações", type="primary", use_container_width=True)

    if submitted:
        db = SessionLocal()
        try:
            editar_fornecedor(
                db,
                usuario_atual,
                fornecedor.id_fornecedor,
                razao_social,
                cnpj,
                email=email,
                telefone=telefone,
            )
            st.toast("Fornecedor atualizado com sucesso!", icon="✅")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao atualizar: {e}")
        finally:
            db.close()


@st.dialog("Excluir Fornecedor")
def modal_excluir_fornecedor(fornecedor, usuario_atual):
    doc_atual = getattr(fornecedor, 'cnpj', getattr(fornecedor, 'cnpj_cpf', ''))
    st.warning(f"Tem certeza que deseja excluir o fornecedor **{fornecedor.razao_social}** ({doc_atual})?")
    st.caption("Esta ação não poderá ser desfeita e falhará caso o fornecedor possua pedidos de compra vinculados.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirmar Exclusão", type="primary", use_container_width=True):
            db = SessionLocal()
            try:
                remover_fornecedor(db, usuario_atual, fornecedor.id_fornecedor)
                st.toast("Fornecedor removido com sucesso!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(str(e))
            finally:
                db.close()
    with col2:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()


def _render_fornecedores(db, usuario_atual) -> None:
    with st.expander("➕ Novo Fornecedor", expanded=False):
        with st.form("cadastro_fornecedor", clear_on_submit=True):
            razao_social = st.text_input("Razão Social *")
            cnpj = st.text_input("CNPJ / CPF *")
            col1, col2 = st.columns(2)
            email = col1.text_input("E-mail")
            telefone = col2.text_input("Telefone")
            enviado = st.form_submit_button("Cadastrar fornecedor", type="primary", use_container_width=True)

        if enviado:
            try:
                criar_fornecedor(
                    db,
                    usuario_atual,
                    razao_social,
                    cnpj,
                    email=email,
                    telefone=telefone,
                )
                st.success("Fornecedor cadastrado com sucesso.")
                st.rerun()
            except Exception as erro:
                st.error(str(erro))

    fornecedores = listar_fornecedores(db)
    st.markdown("### Fornecedores Cadastrados")

    if not fornecedores:
        st.info("Nenhum fornecedor cadastrado.")
        return

    dados_forn = []
    for forn in fornecedores:
        doc = getattr(forn, 'cnpj', getattr(forn, 'cnpj_cpf', '-'))
        dados_forn.append({
            "ID": forn.id_fornecedor,
            "Razão Social": forn.razao_social,
            "CNPJ / CPF": doc,
            "E-mail": forn.email or "-",
            "Telefone": forn.telefone or "-"
        })
    df_forn = pd.DataFrame(dados_forn)
    st.dataframe(df_forn, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.write("#### Ações do Fornecedor")
    col_id, col_ed, col_del, _ = st.columns([3, 2, 2, 3])
    
    with col_id:
        forn_opcoes = {f.id_fornecedor: f"ID {f.id_fornecedor} - {f.razao_social}" for f in fornecedores}
        forn_selecionado_id = st.selectbox("Selecione o Fornecedor:", options=list(forn_opcoes.keys()), format_func=lambda x: forn_opcoes[x], key="sel_forn")
    
    forn_obj = next((f for f in fornecedores if f.id_fornecedor == forn_selecionado_id), None)
    
    with col_ed:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Editar", key="ed_forn_btn", use_container_width=True):
            modal_editar_fornecedor(forn_obj, usuario_atual)
            
    with col_del:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Excluir", key="del_forn_btn", use_container_width=True):
            modal_excluir_fornecedor(forn_obj, usuario_atual)


# ==========================================
# RENDERIZAÇÃO PRINCIPAL
# ==========================================

def render_cadastros(usuario_atual) -> None:
    render_cabecalho(
        "Cadastros",
        "Gerencie clientes, itens/produtos e fornecedores do sistema.",
    )
    db = SessionLocal()
    try:
        aba_clientes, aba_itens, aba_fornecedores = st.tabs(["Clientes", "Itens", "Fornecedores"])
        with aba_clientes:
            _render_clientes(db, usuario_atual)
        with aba_itens:
            _render_itens(db, usuario_atual)
        with aba_fornecedores:
            _render_fornecedores(db, usuario_atual)
    finally:
        db.close()