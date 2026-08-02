from datetime import datetime
from sqlalchemy.orm import Session
from src.database.models.logistica import Entrega, EntregaStatusHistorico
from src.database.models.vendas import PedidoVenda

def criar_entrega_para_pedido(db: Session, id_pedido: int, data_previsao: datetime, valor_frete: float = 0.00):
    """
    Gera um registro de entrega e vincula o pedido a ela.
    """
    pedido = db.query(PedidoVenda).filter(PedidoVenda.id_pedido_venda == id_pedido).first()
    if not pedido:
        raise ValueError(f"Pedido com ID {id_pedido} não encontrado.")
        
    nova_entrega = Entrega(
        data_previsao=data_previsao,
        status_logistica="Pendente",
        valor_frete=valor_frete
    )
    
    db.add(nova_entrega)
    db.flush()    
    pedido.id_entrega = nova_entrega.id_entrega
    
    db.commit()
    db.refresh(nova_entrega)
    return nova_entrega

def atualizar_status_logistica(db: Session, id_entrega: int, novo_status: str, id_usuario: int = None, nome_usuario: str = None):
    entrega = db.query(Entrega).filter(Entrega.id_entrega == id_entrega).first()
    if not entrega:
        raise ValueError(f"Entrega com ID {id_entrega} não encontrada.")
        
    status_validos = ["Pendente", "Em separação", "Enviado", "Entregue"]
    if novo_status not in status_validos:
        raise ValueError(f"Status inválido. Escolha entre: {status_validos}")

    status_anterior = entrega.status_logistica

    entrega.status_logistica = novo_status
    
    if novo_status == "Entregue":
        entrega.data_entrega_realizada = datetime.now()
        if entrega.pedidos:
            for pedido in entrega.pedidos:
                pedido.status_venda = "Concluído"
    elif novo_status == "Enviado":
        entrega.data_expedicao = datetime.now()

    if status_anterior != novo_status:
        registro = EntregaStatusHistorico(
            id_entrega=id_entrega,
            id_usuario=id_usuario,
            nome_usuario=nome_usuario,
            status_anterior=status_anterior,
            status_novo=novo_status,
        )
        db.add(registro)

    db.commit()
    db.refresh(entrega)
    return entrega

def listar_entregas(db: Session, status: str = None):
    query = db.query(Entrega).order_by(Entrega.id_entrega.asc())
    if status:
        query = query.filter(Entrega.status_logistica == status)
    return query.all()

def listar_historico_entrega(db: Session, id_entrega: int):
    """
    Retorna o histórico de mudanças de status de uma entrega, mais recente primeiro.
    """
    return (
        db.query(EntregaStatusHistorico)
        .filter(EntregaStatusHistorico.id_entrega == id_entrega)
        .order_by(EntregaStatusHistorico.data_hora.desc())
        .all()
    )