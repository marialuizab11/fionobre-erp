import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from src.database.connection import SessionLocal
from src.database.models.cadastros import Cliente, Item
from src.services.venda_service import criar_orcamento, criar_pedido_venda
from src.services.logistica_service import criar_entrega_para_pedido
from src.views.components.ui_components import render_cabecalho
from src.services.financeiro_service import criar_conta_a_receber

def resetar_formulario():
    st.session_state.carrinho_itens = []

@st.dialog("Resumo do Pedido")
def modal_resumo_pedido(id_cliente, carrinho_itens, valor_frete, modalidade_entrega,
                        data_previsao_entrega, condicao_pagamento, data_vencimento,
                        usuario_atual):
    st.write("Confira os detalhes do pedido antes de finalizar:")
    
    valor_total_itens = 0
    dados_tabela = []
    
    for item in carrinho_itens:
        subtotal = item['quantidade'] * item['valor_unitario']
        valor_total_itens += subtotal
        dados_tabela.append({
            "Descrição": item['descricao'],
            "Qtd": int(item['quantidade']),
            "Vlr. Un. (R$)": f"{item['valor_unitario']:.2f}",
            "Subtotal (R$)": f"{subtotal:.2f}"
        })
        
    df_itens = pd.DataFrame(dados_tabela)
    st.dataframe(df_itens, use_container_width=True, hide_index=True)
    
    valor_total_compra = valor_total_itens + valor_frete
    
    st.divider()
    
    col_tot_itens, col_tot_frete, col_tot_geral = st.columns(3)
    col_tot_itens.write(f"**Total dos Itens**\nR\\$ {valor_total_itens:.2f}")
    col_tot_frete.write(f"**Valor do Frete**\nR\\$ {valor_frete:.2f}")
    col_tot_geral.write(f"**Total da Compra**\nR\\$ {valor_total_compra:.2f}")
    
    st.divider()
    
    st.subheader("Faturamento e Entrega")
    col_mod, col_cond, col_venc = st.columns(3)
    col_mod.write(f"**Modalidade:**\n{modalidade_entrega}\n\n**Prev. Sistêmica:** {data_previsao_entrega.strftime('%d/%m/%Y')}")
    col_cond.write(f"**Condição:**\n{condicao_pagamento}")
    col_venc.write(f"**Vencimento Base:**\n{data_vencimento.strftime('%d/%m/%Y')}")
    
    st.divider()
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        if st.button("Confirmar Pedido de Venda", type="primary", use_container_width=True):
            db = SessionLocal()
            try:
                carrinho_payload = [
                    {"id_item": i["id_item"], "quantidade": i["quantidade"], "valor_unitario": i["valor_unitario"]}
                    for i in carrinho_itens
                ]
                
                pedido = criar_pedido_venda(
                    db=db,
                    id_cliente=id_cliente,
                    itens_comprados=carrinho_payload,
                    usuario=usuario_atual,
                )
                
                if modalidade_entrega == "Entrega Padrão (Logística Interna / Transportadora)":
                    criar_entrega_para_pedido(
                        db=db,
                        id_pedido=pedido.id_pedido_venda,
                        data_previsao=data_previsao_entrega, 
                        valor_frete=valor_frete
                    )

                criar_conta_a_receber(
                    db=db,
                    id_pedido=pedido.id_pedido_venda,
                    valor_total=valor_total_compra,
                    data_vencimento=data_vencimento,
                    id_usuario=usuario_atual.id_usuario,
                )
                
                st.session_state.carrinho_itens = []
                st.session_state.mensagem_sucesso = f"Pedido #ID {pedido.id_pedido_venda} fechado com sucesso!"
                st.rerun()
                
            except Exception as e:
                st.error(f"Erro ao fechar pedido: {e}")
            finally:
                db.close()

    with col2:
        if st.button("Salvar como Orçamento", use_container_width=True):
            db = SessionLocal()
            try:
                carrinho_payload = [
                    {"id_item": i["id_item"], "quantidade": i["quantidade"], "valor_unitario": i["valor_unitario"]}
                    for i in carrinho_itens
                ]
                orcamento = criar_orcamento(db, id_cliente, carrinho_payload, usuario_atual)
                st.session_state.carrinho_itens = []
                st.session_state.mensagem_sucesso = f"Orçamento #ID {orcamento.id_pedido_venda} gerado com sucesso!"
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao gerar orçamento: {e}")
            finally:
                db.close()

    with col3:
        if st.button("Voltar", use_container_width=True):
            st.rerun()
            
def render_vendas(usuario_atual):
    if "carrinho_itens" not in st.session_state:
        st.session_state.carrinho_itens = []

    if "mensagem_sucesso" in st.session_state:
        st.success(st.session_state.mensagem_sucesso)
        st.toast("Pedido realizado!")
        del st.session_state.mensagem_sucesso

    render_cabecalho("Central de Vendas", "Lance pedidos com múltiplos itens, controle saldos e dispare a logística.")
    
    db = SessionLocal()
    try:
        clientes = db.query(Cliente).all()
        itens = (
            db.query(Item)
            .filter(Item.tipo_item == "PRODUTO_ACABADO")
            .order_by(Item.descricao)
            .all()
        )
        
        if not clientes or not itens:
            st.warning("Aviso: É necessário ter clientes e itens cadastrados no banco. Verifique o painel de estoque.")
            return

        cliente_map = {f"{c.razao_social} (CNPJ/CPF: {c.cnpj_cpf})": c for c in clientes}
        
        cliente_selecionado_str = st.selectbox(
            "Selecione o Cliente", 
            list(cliente_map.keys()),
            on_change=resetar_formulario
        )
        
        cliente_obj = cliente_map[cliente_selecionado_str]
        id_cliente = cliente_obj.id_cliente
        
        st.markdown("---")
        st.subheader("Itens do Pedido (Carrinho)")

        with st.form("form_adicionar_item", clear_on_submit=False):
            item_map = {f"{i.descricao} (Disponível: {i.saldo_estoque} {i.unidade_medida})": i for i in itens}
            item_selecionado_str = st.selectbox("Selecionar produto acabado", list(item_map.keys()))
            
            item_obj = item_map.get(item_selecionado_str)
            
            col_qnt, col_val = st.columns(2)
            with col_qnt:
                quantidade = st.number_input("Quantidade", min_value=0, value=1, step=1, format="%d")
            with col_val:
                preco_unitario = st.number_input("Valor Unitário (R$)", min_value=0.00, value=float(item_obj.preco_venda) if item_obj else 0.00, step=0.01)
                
            btn_adicionar = st.form_submit_button("Adicionar Item ao Carrinho")
            
            if btn_adicionar:
                qtd_ja_no_carrinho = 0
                if item_obj:
                    qtd_ja_no_carrinho = sum(
                        item['quantidade'] for item in st.session_state.carrinho_itens 
                        if item['id_item'] == item_obj.id_item
                    )
                
                qtd_total_desejada = qtd_ja_no_carrinho + float(quantidade)

                if not item_obj:
                    st.error("Erro: Um produto válido deve ser selecionado.")
                elif quantidade <= 0:
                    st.error("Erro: A quantidade deve ser um valor inteiro maior que zero.")
                elif preco_unitario <= 0:
                    st.error("Erro: Valor unitário inválido. Revise os dados e tente novamente.")
                elif qtd_total_desejada > float(item_obj.saldo_estoque):
                    st.error(f"Erro: Estoque insuficiente. Você já tem {qtd_ja_no_carrinho} no carrinho e está tentando adicionar mais {quantidade}. O total do estoque é {item_obj.saldo_estoque}.")
                else:
                    item_existente = next((item for item in st.session_state.carrinho_itens if item['id_item'] == item_obj.id_item), None)
                    
                    if item_existente:
                        item_existente['quantidade'] += float(quantidade)
                        item_existente['valor_unitario'] = float(preco_unitario) 
                        st.success(f"Quantidade do item '{item_obj.descricao}' atualizada no carrinho com sucesso!")
                    else:
                        st.session_state.carrinho_itens.append({
                            "id_item": item_obj.id_item,
                            "descricao": item_obj.descricao,
                            "quantidade": float(quantidade),
                            "valor_unitario": float(preco_unitario),
                            "saldo_disponivel": float(item_obj.saldo_estoque)
                        })
                        st.success(f"Item '{item_obj.descricao}' adicionado ao carrinho com sucesso!")

        if st.session_state.carrinho_itens:
            st.markdown("#### Itens na Composição do Pedido:")
            
            for idx, item_carrinho in enumerate(st.session_state.carrinho_itens):
                cols = st.columns([3, 1, 1, 1])
                with cols[0]:
                    st.write(f"**{item_carrinho['descricao']}**")
                with cols[1]:
                    st.write(f"Qtd: {item_carrinho['quantidade']}")
                with cols[2]:
                    st.write(f"R$ {item_carrinho['valor_unitario']:.2f}")
                with cols[3]:
                    if st.button("Remover", key=f"rem_{idx}"):
                        st.session_state.carrinho_itens.pop(idx)
                        st.rerun()
            
            st.markdown("---")
            
            st.subheader("Logística")
            
            modalidade_entrega = st.radio(
                "Modalidade de Entrega", 
                options=["Entrega Padrão (Logística Interna / Transportadora)", "Retirada na Loja / Frete Externo"],
                horizontal=True
            )
            
            if modalidade_entrega == "Entrega Padrão (Logística Interna / Transportadora)":
                data_previsao_entrega = datetime.now() + timedelta(days=9)
                valor_frete = st.number_input("Valor do Frete (R$)", value=0.00, step=10.0)
                
                endereco_completo = f"{cliente_obj.rua or 'N/A'}, {cliente_obj.numero or 'S/N'} - {cliente_obj.bairro or 'N/A'}, {cliente_obj.cidade or 'N/A'} - {cliente_obj.uf or 'N/A'} (CEP: {cliente_obj.cep or 'N/A'})"
                st.info(f"Endereço de Entrega (Base Cadastral):\n\n{endereco_completo}\n\n**Prazo Estimado:** 9 dias úteis (Previsão: {data_previsao_entrega.strftime('%d/%m/%Y')})")
            else:
                data_previsao_entrega = datetime.now() + timedelta(days=1)
                valor_frete = 0.00
                st.info(f"Retirada / Externa: O frete será isento (R$ 0,00) e a logística é de responsabilidade do cliente.\n\n**Prazo para Separação:** 1 dia útil (Previsão: {data_previsao_entrega.strftime('%d/%m/%Y')})")
                
            st.markdown("---")
            
            st.subheader("Faturamento")
            col_cond, col_venc = st.columns(2)
            with col_cond:
                condicao_pagamento = st.selectbox(
                    "Condição de Pagamento", 
                    ["À vista", "Pix", "Boleto 30 dias", "Boleto 30/60 dias", "Cartão de Crédito"]
                )
            with col_venc:
                data_vencimento = st.date_input(
                    "Data de Vencimento Base", 
                    value=datetime.now() + timedelta(days=30),
                    format="DD/MM/YYYY"
                )
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("Revisar e Finalizar Pedido", type="primary"):
                if len(st.session_state.carrinho_itens) == 0:
                    st.error("Erro: A venda deve conter pelo menos um item associado.")
                elif valor_frete < 0:
                    st.error("Erro: O valor do frete não pode ser negativo.")
                else:
                    modal_resumo_pedido(
                        id_cliente, 
                        st.session_state.carrinho_itens, 
                        valor_frete, 
                        modalidade_entrega,
                        data_previsao_entrega,
                        condicao_pagamento, 
                        data_vencimento,
                        usuario_atual,
                    )
        else:
            st.info("Informação: O carrinho está vazio. Adicione pelo menos um produto para conseguir finalizar a venda.")

    except Exception as e:
        st.error(f"Erro na tela de vendas: {e}")
    finally:
        db.close()
