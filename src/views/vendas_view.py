import streamlit as st
from datetime import datetime, timedelta
from src.database.connection import SessionLocal
from src.database.models.cadastros import Cliente, Item
from src.services.venda_service import criar_pedido_venda
from src.services.logistica_service import criar_entrega_para_pedido
from src.views.components.ui_components import render_cabecalho

def render_vendas():
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
                # 1. Verifica a quantidade deste item que JÁ ESTÁ no carrinho (antes da validação principal)
                qtd_ja_no_carrinho = 0
                if item_obj:
                    qtd_ja_no_carrinho = sum(
                        item['quantidade'] for item in st.session_state.carrinho_itens 
                        if item['id_item'] == item_obj.id_item
                    )
                
                qtd_total_desejada = qtd_ja_no_carrinho + float(quantidade)

                # Validações estruturadas com if/elif em vez de st.stop()
                if not item_obj:
                    st.error("❌ Um produto válido deve ser selecionado.")
                elif quantidade <= 0:
                    st.error("❌ A quantidade deve ser um valor inteiro maior que zero.")
                elif preco_unitario <= 0:
                    st.error("❌ Valor unitário inválido. Revise os dados e tente novamente.")
                elif qtd_total_desejada > float(item_obj.saldo_estoque):
                    st.error(f"❌ Estoque insuficiente. Você já tem {qtd_ja_no_carrinho} no carrinho e está tentando adicionar mais {quantidade}. O total do estoque é {item_obj.saldo_estoque}.")
                else:
                    # Se chegou no else, todas as validações passaram
                    item_existente = next((item for item in st.session_state.carrinho_itens if item['id_item'] == item_obj.id_item), None)
                    
                    if item_existente:
                        item_existente['quantidade'] += float(quantidade)
                        # Atualiza o preço unitário para refletir a última alteração, se houver
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

        # Exibe os itens já adicionados no carrinho (continua renderizando normalmente)
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
            
            # Removido min_value para permitir validação manual
            valor_frete = st.number_input("Valor do Frete (R$)", value=0.00, step=10.0)
            
            if st.button("Finalizar e Confirmar Pedido de Venda", type="primary"):
                # Validações de fechamento
                if len(st.session_state.carrinho_itens) == 0:
                    st.error("❌ A venda deve conter pelo menos um item associado.")
                elif valor_frete < 0:
                    st.error("❌ O valor do frete não pode ser negativo.")
                else:
                    try:
                        # Prepara o formato esperado pelo backend
                        carrinho_payload = [
                            {
                                "id_item": i["id_item"],
                                "quantidade": i["quantidade"],
                                "valor_unitario": i["valor_unitario"]
                            }
                            for i in st.session_state.carrinho_itens
                        ]
                        
                        # 1. Cria o pedido e abate estoques no backend
                        pedido = criar_pedido_venda(
                            db=db,
                            id_cliente=id_cliente,
                            itens_comprados=carrinho_payload,
                            id_usuario=1
                        )
                        
                        # 2. Gera a entrega vinculada
                        data_previsao_entrega = datetime.now() + timedelta(days=3)
                        criar_entrega_para_pedido(
                            db=db,
                            id_pedido=pedido.id_pedido_venda,
                            data_previsao=data_previsao_entrega,
                            valor_frete=valor_frete
                        )
                        
                        st.success(f"✅ Pedido #ID {pedido.id_pedido_venda} fechado com sucesso! Valor Total: R$ {pedido.valor_total_pedido:.2f}")
                        st.balloons()
                        
                        # Limpa o carrinho após o sucesso
                        st.session_state.carrinho_itens = []
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Erro ao fechar pedido: {e}")
        else:
            st.info("ℹ️ O carrinho está vazio. Adicione pelo menos um produto para conseguir finalizar a venda.")

    except Exception as e:
        st.error(f"Erro na tela de vendas: {e}")
    finally:
        db.close()