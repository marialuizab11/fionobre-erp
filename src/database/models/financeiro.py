from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database.models.base import Base

class LancamentoFinanceiro(Base):
    __tablename__ = 'lancamento_financeiro'

    id_lancamento = Column(Integer, primary_key=True, autoincrement=True)

    id_pedido_venda = Column(Integer, ForeignKey('pedido_venda.id_pedido_venda'), nullable=True)
    id_pedido_compra = Column(Integer, ForeignKey('pedido_compra.id_pedido_compra'), nullable=True)

    valor = Column(Numeric(10, 2), nullable=False)
    data_vencimento = Column(DateTime, nullable=False)
    data_pagamento = Column(DateTime, nullable=True)

    tipo_lancamento = Column(String(50), nullable=False) 
    origem_lancamento = Column(String(50), nullable=False)  
    status_pagamento = Column(String(50), default='Pendente') 

    pedido_venda = relationship("PedidoVenda", back_populates="lancamentos")
    pedido_compra = relationship("PedidoCompra", back_populates="lancamentos")
