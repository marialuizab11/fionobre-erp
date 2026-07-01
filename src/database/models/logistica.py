from sqlalchemy import Column, Integer, String, Numeric, DateTime
from sqlalchemy.orm import relationship
from src.database.models.base import Base

class Entrega(Base):
    __tablename__ = 'entrega'
    
    id_entrega = Column(Integer, primary_key=True, autoincrement=True)
    id_transportadora = Column(Integer, nullable=True) # Será uma FK para o cadastro de transportadoras
    
    # Atributos temporais e operacionais vindos do seu MER
    data_previsao = Column(DateTime, nullable=False)
    data_expedicao = Column(DateTime, nullable=True)
    data_entrega_realizada = Column(DateTime, nullable=True)
    
    status_logistica = Column(String(50), default='Pendente') # Pendente, Expedido, Entregue
    valor_frete = Column(Numeric(10, 2), default=0.00)
    
    # Relacionamento 1:N -> Uma entrega (caminhão) pode conter vários pedidos de venda agrupados
    pedidos = relationship("PedidoVenda", back_populates="entrega")