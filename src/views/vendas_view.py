import streamlit as st
from datetime import datetime, timedelta
from src.database.connection import SessionLocal
from src.database.models.cadastros import Cliente, Item
from src.services.venda_service import criar_pedido_venda
from src.services.logistica_service import criar_entrega_para_pedido
from src.views.components.ui_components import render_cabecalho

@st.dialog("Resumo do Pedido")
def modal_resumo_pedido(id_cliente, carrinho_itens, valor_frete):
    st.write("Confira os detalhes do pedido antes de finalizar:")
    
    valor_total_itens = 0
    for item in carrinho_itens:
        subtotal = item['quantidade'] * item['valor_unitario']
        valor_total_itens += subtotal
        # O cifrão está escapado com \ para evitar o modo LaTeX do Streamlit
        st.write(f"- {int(item['quantidade'])}x {item['descricao']} (R\\$ {item['valor_unitario']:.2f} un) = **R\\$ {subtotal:.2f}**")
    
    valor_total_compra = valor_total_itens + valor_frete
    
    st.markdown("---")
    st.write(f"**Total dos Itens:** R\\$ {valor_total_itens:.2f}")
    st.write(f"**Valor do Frete:** R\\$ {valor_frete:.2f}")
    st.subheader(f"Total da Compra: R\\$ {valor_total_compra:.2f}")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Confirmar Pedido", type="primary", use_container_width=True):
            db = SessionLocal()
            try:
                carrinho_payload = [
                    {
                        "id_item": i["id_item"],
                        "quantidade": i["quantidade"],
                        "valor_unitario": i["valor_unitario"]
                    }
                    for i in carrinho_itens
                ]
                
                pedido = criar_pedido_venda(
                    db=db,
                    id_cliente=id_cliente,
                    itens_comprados=carrinho_payload,
                    id_usuario=1
                )
                
                data_previsao_entrega = datetime.now() + timedelta(days=3)
                criar_entrega_para_pedido(
                    db=db,
                    id_pedido=pedido.id_pedido_venda,
                    data_previsao=data_previsao_entrega,
                    valor_frete=valor_frete
                )
                
                st.session_state.carrinho_itens = []
                st.session_state.mensagem_sucesso = f"✅ Pedido #ID {pedido.id_pedido_venda} fechado com sucesso! Valor Total: R$ {pedido.valor_total_pedido:.2f}"
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Erro ao fechar pedido: {e}")
            finally:
                db.close()
                
    with col2:
        if st.button("❌ Cancelar", use_container_width=True):
            st.rerun()


def render_vendas():
    # Exibe a notificação de sucesso se a variável foi definida no modal
    if "mensagem_sucesso" in st.session_state:
        st.success(st.session_state.mensagem_sucesso)
        st.balloons()
        del st.session_state.mensagem_sucesso

    render_cabecalho("Central de Vendas", "Lance pedidos com múltiplos itens, controle saldos e dispare a logística.")
    
    db = SessionLocal()
    try:
        clientes = db.query(Cliente).all()
        itens = db.query(Item).all()
        
        if not clientes or not itens:
            st.warning("⚠️ É necessário ter clientes e itens cadastrados no banco. Verifique o painel de estoque.")
            return

        # Seleção de Cliente
        cliente_map = {f"{c.razao_social} (CNPJ/CPF: {c.cnpj_cpf})": c.id_cliente for c in clientes}
        cliente_selecionado_str = st.selectbox("Selecione o Cliente", list(cliente_map.keys()))
        id_cliente = cliente_map[cliente_selecionado_str]
        
        st.markdown("---")
        st.subheader("📦 Itens do Pedido (Carrinho)")

        # Inicializa o carrinho na sessão do Streamlit
        if "carrinho_itens" not in st.session_state:
            st.session_state.carrinho_itens = []

        # Formulário para adicionar um item à lista temporária
        with st.form("form_adicionar_item", clear_on_submit=False):
            item_map = {f"{i.descricao} (Disponível: {i.saldo_estoque} {i.unidade_medida})": i for i in itens}
            item_selecionado_str = st.selectbox("Selecionar Produto / Matéria-Prima", list(item_map.keys()))
            
            # Garante que um item foi de fato selecionado
            item_obj = item_map.get(item_selecionado_str)
            
            col_qnt, col_val = st.columns(2)
            with col_qnt:
                quantidade = st.number_input("Quantidade", min_value=0, value=1, step=1, format="%d")
            with col_val:
                preco_unitario = st.number_input("Valor Unitário (R$)", min_value=0.00, value=float(item_obj.preco_venda) if item_obj else 0.00, step=0.01)
                
            btn_adicionar = st.form_submit_button("➕ Adicionar Item ao Carrinho")
            
            if btn_adicionar:
                # 1. Verifica a quantidade deste item que JÁ ESTÁ no carrinho
                qtd_ja_no_carrinho = 0
                if item_obj:
                    qtd_ja_no_carrinho = sum(
                        item['quantidade'] for item in st.session_state.carrinho_itens 
                        if item['id_item'] == item_obj.id_item
                    )
                
                qtd_total_desejada = qtd_ja_no_carrinho + float(quantidade)

                # Validações estruturadas
                if not item_obj:
                    st.error("❌ Um produto válido deve ser selecionado.")
                elif quantidade <= 0:
                    st.error("❌ A quantidade deve ser um valor inteiro maior que zero.")
                elif preco_unitario <= 0:
                    st.error("❌ Valor unitário inválido. Revise os dados e tente novamente.")
                elif qtd_total_desejada > float(item_obj.saldo_estoque):
                    st.error(f"❌ Estoque insuficiente. Você já tem {qtd_ja_no_carrinho} no carrinho e está tentando adicionar mais {quantidade}. O total do estoque é {item_obj.saldo_estoque}.")
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

        # Exibe os itens já adicionados no carrinho
        if st.session_state.carrinho_itens:
            st.markdown("#### Itens na Composição do Pedido:")
            
            # Tabela resumida do carrinho
            for idx, item_carrinho in enumerate(st.session_state.carrinho_itens):
                cols = st.columns([3, 1, 1, 1])
                with cols[0]:
                    st.write(f"**{item_carrinho['descricao']}**")
                with cols[1]:
                    st.write(f"Qtd: {item_carrinho['quantidade']}")
                with cols[2]:
                    st.write(f"R$ {item_carrinho['valor_unitario']:.2f}")
                with cols[3]:
                    if st.button("🗑️ Remover", key=f"rem_{idx}"):
                        st.session_state.carrinho_itens.pop(idx)
                        st.rerun()
            
            st.markdown("---")
            st.subheader("🚚 Dados Logísticos e Fechamento")
            
            valor_frete = st.number_input("Valor do Frete (R$)", value=0.00, step=10.0)
            
            # Botão que agora chama o modal ao invés de processar o backend direto
            if st.button("Finalizar e Confirmar Pedido de Venda", type="primary"):
                # Validações de fechamento antes de abrir o modal
                if len(st.session_state.carrinho_itens) == 0:
                    st.error("❌ A venda deve conter pelo menos um item associado.")
                elif valor_frete < 0:
                    st.error("❌ O valor do frete não pode ser negativo.")
                else:
                    # Chama o modal e passa os dados atuais para a tela de confirmação
                    modal_resumo_pedido(id_cliente, st.session_state.carrinho_itens, valor_frete)
        else:
            st.info("ℹ️ O carrinho está vazio. Adicione pelo menos um produto para conseguir finalizar a venda.")

    except Exception as e:
        st.error(f"Erro na tela de vendas: {e}")
    finally:
        db.close()