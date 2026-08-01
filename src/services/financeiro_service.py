from datetime import datetime
from sqlalchemy.orm import Session
# Ajuste o caminho de importação da model LancamentoFinanceiro de acordo com a sua base
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