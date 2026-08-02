from sqlalchemy.orm import Session
from src.database.models.vendas import PedidoVenda, ItemVenda
from src.services.estoque_service import baixar_estoque

def criar_pedido_venda(db: Session, id_cliente: int, itens_comprados: list, id_usuario: int = 1):
    """
    Processa a criação completa de um Pedido de Venda e dispara a baixa de estoque.
    'itens_comprados' = [{"id_item": 1, "quantidade": 2.0, "valor_unitario": 80.00}, ...]
    """
    if not itens_comprados:
        raise ValueError("Um pedido precisa ter pelo menos um item.")
        
    novo_pedido = PedidoVenda(
        id_cliente=id_cliente,
        id_usuario=id_usuario,
        status_venda="Confirmado",
        valor_total_pedido=0.00
    )
    
    db.add(novo_pedido)
    db.flush()  # Gera o id do pedido
    
    valor_total_acumulado = 0.00
    
    for linha in itens_comprados:
        id_item = linha["id_item"]
        qtd = linha["quantidade"]
        preco_un = linha["valor_unitario"]
        
        # Dispara a baixa e validação de estoque
        baixar_estoque(db=db, id_item=id_item, quantidade=qtd, id_usuario=id_usuario)
        
        subtotal = qtd * preco_un
        valor_total_acumulado += subtotal
        
        novo_item_venda = ItemVenda(
            id_pedido_venda=novo_pedido.id_pedido_venda,
            id_item=id_item,
            quantidade_vendida=qtd,
            valor_unitario=preco_un
        )
        db.add(novo_item_venda)
        
    novo_pedido.valor_total_pedido = valor_total_acumulado
    
    try:
        db.commit()
        db.refresh(novo_pedido)
        return novo_pedido
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao processar a venda no banco: {e}")