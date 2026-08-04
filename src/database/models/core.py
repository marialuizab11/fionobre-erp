from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database.models.base import Base

class MovimentacaoEstoque(Base):
    __tablename__ = 'movimentacao_estoque'
    
    id_movimentacao = Column(Integer, primary_key=True, autoincrement=True)
    id_item = Column(Integer, ForeignKey('item.id_item'), nullable=False)
    id_usuario = Column(Integer, ForeignKey('usuario.id_usuario'), nullable=False)
    
    # Novos campos para controle de localização e transferências
    id_local_origem = Column(Integer, ForeignKey('localizacao_estoque.id_localizacao'), nullable=True)
    id_local_destino = Column(Integer, ForeignKey('localizacao_estoque.id_localizacao'), nullable=True)
    
    quantidade = Column(Numeric(10, 2), nullable=False)
    tipo_movimento = Column(String(50), nullable=False) # Ex: 'SAIDA_VENDA', 'ENTRADA_COMPRA', 'TRANSFERENCIA', 'AJUSTE'
    data_movimento = Column(DateTime, default=datetime.utcnow)
    observacao = Column(String(255), nullable=True) # Motivo do ajuste manual ou ref do inventário
    
    # Relacionamentos
    item = relationship("Item", back_populates="movimentacoes")
    usuario = relationship("Usuario", back_populates="movimentacoes_estoque")
    local_origem = relationship("LocalizacaoEstoque", foreign_keys=[id_local_origem])
    local_destino = relationship("LocalizacaoEstoque", foreign_keys=[id_local_destino])