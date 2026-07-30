from datetime import datetime
from sqlalchemy.orm import Session
from src.database.models.logistica import Entrega
from src.database.models.vendas import PedidoVenda

def criar_entrega_para_pedido(db: Session, id_pedido: int, data_previsao: datetime, valor_frete: float = 0.00):
    """
    Gera um registro de entrega e vincula o pedido a ela.
    """
    # 1. Verifica se o pedido existe
    pedido = db.query(PedidoVenda).filter(PedidoVenda.id_pedido_venda == id_pedido).first()
    if not pedido:
        raise ValueError(f"Pedido com ID {id_pedido} não encontrado.")
        
    # 2. Instancia a entrega conforme os campos reais do modelo
    nova_entrega = Entrega(
        data_previsao=data_previsao,
        status_logistica="Pendente",
        valor_frete=valor_frete
    )
    
    db.add(nova_entrega)
    db.flush() # Gera o id_entrega para vincular ao pedido
    
    # 3. Vincula o pedido à entrega criada
    pedido.id_entrega = nova_entrega.id_entrega
    
    db.commit()
    db.refresh(nova_entrega)
    return nova_entrega

def atualizar_status_logistica(db: Session, id_entrega: int, novo_status: str):
    """
    Atualiza o status logístico da entrega (ex: 'Pendente', 'Expedido', 'Entregue').
    """
    entrega = db.query(Entrega).filter(Entrega.id_entrega == id_entrega).first()
    if not entrega:
        raise ValueError(f"Entrega com ID {id_entrega} não encontrada.")
        
    status_validos = ["Pendente", "Expedido", "Entregue"]
    if novo_status not in status_validos:
        raise ValueError(f"Status inválido. Escolha entre: {status_validos}")
        
    entrega.status_logistica = novo_status
    
    # Se foi entregue, preenche a data real de entrega
    if novo_status == "Entregue":
        entrega.data_entrega_realizada = datetime.now()
    elif novo_status == "Expedido":
        entrega.data_expedicao = datetime.now()
        
    db.commit()
    db.refresh(entrega)
    return entrega