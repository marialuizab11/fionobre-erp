import streamlit as st

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

    c_head = st.columns([1, 3, 2, 2.5, 2, 1.5])
    c_head[0].write("**ID**")
    c_head[1].write("**Nome/Razão Social**")
    c_head[2].write("**CPF/CNPJ**")
    c_head[3].write("**E-mail**")
    c_head[4].write("**Cidade/UF**")
    c_head[5].write("**Ações**")
    st.markdown("---")

    for cli in clientes:
        c_row = st.columns([1, 3, 2, 2.5, 2, 1.5])
        c_row[0].write(str(cli.id_cliente))
        c_row[1].write(cli.razao_social)
        c_row[2].write(cli.cnpj_cpf)
        c_row[3].write(cli.email or "-")
        c_row[4].write(f"{cli.cidade or '-'}/{cli.uf or '-'}")
        
        with c_row[5]:
            with st.popover("⋮", use_container_width=True):
                if st.button("Editar", key=f"ed_cli_{cli.id_cliente}", use_container_width=True):
                    modal_editar_cliente(cli, usuario_atual)
                if st.button("Excluir", key=f"del_cli_{cli.id_cliente}", use_container_width=True):
                    modal_excluir_cliente(cli, usuario_atual)


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

    c_head = st.columns([1, 3, 2, 1.5, 1.5, 1.5, 1.5])
    c_head[0].write("**ID**")
    c_head[1].write("**Descrição**")
    c_head[2].write("**Tipo**")
    c_head[3].write("**Saldo**")
    c_head[4].write("**Preço (R$)**")
    c_head[5].write("**Custo (R$)**")
    c_head[6].write("**Ações**")
    st.markdown("---")

    for item in itens:
        c_row = st.columns([1, 3, 2, 1.5, 1.5, 1.5, 1.5])
        c_row[0].write(str(item.id_item))
        c_row[1].write(item.descricao)
        c_row[2].write(item.tipo_item)
        c_row[3].write(f"{float(item.saldo_estoque):.2f} {item.unidade_medida}")
        c_row[4].write(f"{float(item.preco_venda):.2f}")
        c_row[5].write(f"{float(item.custo_medio):.2f}")
        
        with c_row[6]:
            with st.popover("⋮", use_container_width=True):
                if st.button("Editar", key=f"ed_itm_{item.id_item}", use_container_width=True):
                    modal_editar_item(item, usuario_atual)
                if st.button("Excluir", key=f"del_itm_{item.id_item}", use_container_width=True):
                    modal_excluir_item(item, usuario_atual)


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

    c_head = st.columns([1, 3, 2, 2, 2, 1.5])
    c_head[0].write("**ID**")
    c_head[1].write("**Razão Social**")
    c_head[2].write("**CNPJ / CPF**")
    c_head[3].write("**E-mail**")
    c_head[4].write("**Telefone**")
    c_head[5].write("**Ações**")
    st.markdown("---")

    for forn in fornecedores:
        c_row = st.columns([1, 3, 2, 2, 2, 1.5])
        c_row[0].write(str(forn.id_fornecedor))
        c_row[1].write(forn.razao_social)
        doc = getattr(forn, 'cnpj', getattr(forn, 'cnpj_cpf', '-'))
        c_row[2].write(doc)
        c_row[3].write(forn.email or "-")
        c_row[4].write(forn.telefone or "-")
        
        with c_row[5]:
            with st.popover("⋮", use_container_width=True):
                if st.button("Editar", key=f"ed_forn_{forn.id_fornecedor}", use_container_width=True):
                    modal_editar_fornecedor(forn, usuario_atual)
                if st.button("Excluir", key=f"del_forn_{forn.id_fornecedor}", use_container_width=True):
                    modal_excluir_fornecedor(forn, usuario_atual)


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