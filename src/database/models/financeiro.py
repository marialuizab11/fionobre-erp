from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database.models.base import Base

class LancamentoFinanceiro(Base):
    __tablename__ = 'lancamento_financeiro'
    
    id_lancamento = Column(Integer, primary_key=True, autoincrement=True)
    
    # Chaves estrangeiras (nullable=True porque um lançamento pode vir de Venda OU de Compra)
    id_pedido_venda = Column(Integer, ForeignKey('pedido_venda.id_pedido_venda'), nullable=True)
    # id_pedido_compra = Column(Integer, ForeignKey('pedido_compra.id_pedido_compra'), nullable=True) # Para o futuro
    
    valor = Column(Numeric(10, 2), nullable=False)
    data_vencimento = Column(DateTime, nullable=False)
    data_pagamento = Column(DateTime, nullable=True)
    tipo_lancamento = Column(String(50), nullable=False) # Ex: 'CONTA_A_RECEBER', 'CONTA_A_PAGAR'
    status_pagamento = Column(String(50), default='Pendente') # Ex: 'Pendente', 'Pago', 'Cancelado'
    
    # Relacionamento reverso com Pedido de Venda
    pedido_venda = relationship("PedidoVenda", back_populates="lancamentos")