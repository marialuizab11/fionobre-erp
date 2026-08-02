from datetime import datetime, time
from sqlalchemy.orm import Session
from src.database.models.vendas import PedidoVenda, ItemVenda, PedidoVendaHistorico
from src.database.models.logistica import Entrega
from src.database.models.financeiro import LancamentoFinanceiro
from src.services.estoque_service import baixar_estoque, estornar_estoque

def criar_pedido_venda(db: Session, id_cliente: int, itens_comprados: list, id_usuario: int = 1, nome_usuario: str = None):
    if not itens_comprados:
        raise ValueError("Um pedido precisa ter pelo menos um item.")
        
    novo_pedido = PedidoVenda(
        id_cliente=id_cliente,
        id_usuario=id_usuario,
        status_venda="Confirmado",
        valor_total_pedido=0.00
    )
    
    db.add(novo_pedido)
    db.flush() 
    
    valor_total_acumulado = 0.00
    
    for linha in itens_comprados:
        id_item = linha["id_item"]
        qtd = linha["quantidade"]
        preco_un = linha["valor_unitario"]
        
        baixar_estoque(db=db, id_item=id_item, quantidade_venda=qtd, id_usuario=id_usuario)
        
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
    
    log_criacao = PedidoVendaHistorico(
        id_pedido_venda=novo_pedido.id_pedido_venda,
        id_usuario=id_usuario,
        nome_usuario=nome_usuario,
        status_anterior=None,
        status_novo="Confirmado",
        justificativa="Criação do pedido"
    )
    db.add(log_criacao)
    
    try:
        db.commit()
        db.refresh(novo_pedido)
        return novo_pedido
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao processar a venda no banco: {e}")

def cancelar_venda(db: Session, id_pedido: int, justificativa: str, id_usuario: int = 1, nome_usuario: str = None):
    pedido = db.query(PedidoVenda).filter(PedidoVenda.id_pedido_venda == id_pedido).first()
    if not pedido:
        raise ValueError(f"Pedido com ID {id_pedido} não encontrado.")
        
    if pedido.status_venda in ["Cancelado", "Concluído"]:
        raise ValueError(f"O pedido não pode ser cancelado pois o status atual é '{pedido.status_venda}'.")
        
    if not justificativa or len(justificativa.strip()) < 5:
        raise ValueError("É obrigatório fornecer uma justificativa válida para o cancelamento.")

    entrega = None
    if pedido.id_entrega:
        entrega = db.query(Entrega).filter(Entrega.id_entrega == pedido.id_entrega).first()
        if entrega and entrega.status_logistica in ["Enviado", "Entregue"]:
            raise ValueError("O pedido não pode ser cancelado pois a mercadoria já está em trânsito ou foi entregue.")

    status_antigo = pedido.status_venda
    pedido.status_venda = "Cancelado"
    pedido.justificativa_cancelamento = justificativa

    log_cancelamento = PedidoVendaHistorico(
        id_pedido_venda=id_pedido,
        id_usuario=id_usuario,
        nome_usuario=nome_usuario,
        status_anterior=status_antigo,
        status_novo="Cancelado",
        justificativa=justificativa
    )
    db.add(log_cancelamento)

    itens_vendidos = db.query(ItemVenda).filter(ItemVenda.id_pedido_venda == id_pedido).all()
    for item in itens_vendidos:
        estornar_estoque(
            db=db, 
            id_item=item.id_item, 
            quantidade_devolvida=item.quantidade_vendida, 
            id_usuario=id_usuario
        )

    if entrega:
        entrega.status_logistica = "Falha" 

    lancamentos = db.query(LancamentoFinanceiro).filter(LancamentoFinanceiro.id_pedido_venda == id_pedido).all()
    for lancamento in lancamentos:
        if lancamento.status_pagamento == "Pendente":
            lancamento.status_pagamento = "Cancelado"

    try:
        db.commit()
        db.refresh(pedido)
        return pedido
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao processar o cancelamento da venda: {e}")

def listar_pedidos(db: Session, status: str = None, data_inicio: datetime = None, data_fim: datetime = None):
    query = db.query(PedidoVenda)
    
    if status:
        query = query.filter(PedidoVenda.status_venda == status)
        
    if data_inicio:
        data_inicio_completa = datetime.combine(data_inicio, time.min)
        query = query.filter(PedidoVenda.data_venda >= data_inicio_completa)
        
    if data_fim:
        data_fim_completa = datetime.combine(data_fim, time.max)
        query = query.filter(PedidoVenda.data_venda <= data_fim_completa)
        
    return query.order_by(PedidoVenda.data_venda.desc()).all()

def listar_historico_pedido(db: Session, id_pedido: int):
    return (
        db.query(PedidoVendaHistorico)
        .filter(PedidoVendaHistorico.id_pedido_venda == id_pedido)
        .order_by(PedidoVendaHistorico.data_hora.desc())
        .all()
    )