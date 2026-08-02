from decimal import Decimal
from sqlalchemy.orm import Session
from src.database.models.cadastros import Item
from src.database.models.core import MovimentacaoEstoque

def baixar_estoque(db: Session, id_item: int, quantidade_venda: float, id_usuario: int = 1):
    """
    Deduz a quantidade vendida do saldo atual do item e registra o histórico.
    """
    item = db.query(Item).filter(Item.id_item == id_item).first()
    if not item:
        raise ValueError(f"Item com ID {id_item} não foi encontrado.")
    
    qtd_decimal = Decimal(str(quantidade_venda))
    
    if item.saldo_estoque < qtd_decimal:
        raise ValueError(
            f"Saldo insuficiente para o item '{item.descricao}'. "
            f"Disponível: {item.saldo_estoque}, Solicitado: {qtd_decimal}"
        )
        
    item.saldo_estoque -= qtd_decimal
    
    nova_movimentacao = MovimentacaoEstoque(
        id_item=id_item,
        id_usuario=id_usuario,
        quantidade=qtd_decimal,
        tipo_movimento="SAIDA_VENDA"
    )
    
    db.add(nova_movimentacao)

def estornar_estoque(db: Session, id_item: int, quantidade_devolvida: float, id_usuario: int = 1):
    """
    Devolve a quantidade ao saldo de estoque em caso de cancelamento e registra o histórico.
    """
    item = db.query(Item).filter(Item.id_item == id_item).first()
    if not item:
        raise ValueError(f"Produto/Insumo com ID {id_item} não encontrado no estoque.")
        
    qtd_decimal = Decimal(str(quantidade_devolvida))
    
    item.saldo_estoque += qtd_decimal
    
    nova_movimentacao = MovimentacaoEstoque(
        id_item=id_item,
        id_usuario=id_usuario,
        quantidade=qtd_decimal,
        tipo_movimento="ENTRADA_CANCELAMENTO"
    )
    
    db.add(nova_movimentacao)
    db.flush()
    
    return item