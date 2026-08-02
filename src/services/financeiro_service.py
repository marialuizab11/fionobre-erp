from datetime import datetime
from sqlalchemy.orm import Session
from src.database.models.financeiro import LancamentoFinanceiro 

def criar_conta_a_receber(
    db: Session, 
    id_pedido: int, 
    valor_total: float, 
    data_vencimento: datetime
):
    """
    Gera um lançamento financeiro de receita (conta a receber) vinculado ao pedido de venda.
    """
    novo_lancamento = LancamentoFinanceiro(
        id_pedido_venda=id_pedido,
        valor=valor_total,
        data_vencimento=data_vencimento,
        tipo_lancamento="CONTA_A_RECEBER",
        status_pagamento="Pendente"
    )
    
    db.add(novo_lancamento)
    db.commit()
    db.refresh(novo_lancamento)
    
    return novo_lancamento

def listar_lancamentos(
    db: Session, 
    tipo_lancamento: str = "CONTA_A_RECEBER", 
    status: str = None, 
    apenas_vencidas: bool = False
):
    """
    Lista os lançamentos financeiros, podendo filtrar por tipo, status e se estão vencidos.
    """
    query = db.query(LancamentoFinanceiro).filter(LancamentoFinanceiro.tipo_lancamento == tipo_lancamento)
    
    if status:
        query = query.filter(LancamentoFinanceiro.status_pagamento == status)
        
    if apenas_vencidas:
        query = query.filter(
            LancamentoFinanceiro.status_pagamento == "Pendente",
            LancamentoFinanceiro.data_vencimento < datetime.now()
        )
        
    return query.order_by(LancamentoFinanceiro.data_vencimento.asc()).all()

def registrar_pagamento(db: Session, id_lancamento: int):
    """
    Dá baixa em um lançamento financeiro pendente, marcando como Pago e salvando a data.
    """
    lancamento = db.query(LancamentoFinanceiro).filter(LancamentoFinanceiro.id_lancamento == id_lancamento).first()
    
    if not lancamento:
        raise ValueError(f"Lançamento financeiro #{id_lancamento} não encontrado.")
        
    if lancamento.status_pagamento == "Pago":
        raise ValueError("Este lançamento já consta como pago no sistema.")
        
    if lancamento.status_pagamento == "Cancelado":
        raise ValueError("Não é possível baixar um lançamento cancelado.")
        
    lancamento.status_pagamento = "Pago"
    lancamento.data_pagamento = datetime.now()
    
    try:
        db.commit()
        db.refresh(lancamento)
        return lancamento
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao registrar o pagamento no banco: {e}")