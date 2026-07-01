from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database.models.base import Base

class MovimentacaoEstoque(Base):
    __tablename__ = 'movimentacao_estoque'
    
    id_movimentacao = Column(Integer, primary_key=True, autoincrement=True)
    id_item = Column(Integer, ForeignKey('item.id_item'), nullable=False)
    id_usuario = Column(Integer, nullable=False) # ID vindo do Login Google
    
    quantidade = Column(Numeric(10, 2), nullable=False)
    tipo_movimento = Column(String(50), nullable=False) # Ex: 'SAIDA_VENDA', 'ENTRADA_COMPRA'
    data_movimento = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamento com o Item do cadastro
    item = relationship("Item", back_populates="movimentacoes")