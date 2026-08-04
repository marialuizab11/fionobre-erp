from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database.models.base import Base

class Entrega(Base):
    __tablename__ = 'entrega'
    
    id_entrega = Column(Integer, primary_key=True, autoincrement=True)
    id_transportadora = Column(Integer, nullable=True) # Será uma FK para o cadastro de transportadoras
    
    data_previsao = Column(DateTime, nullable=False)
    data_expedicao = Column(DateTime, nullable=True)
    data_entrega_realizada = Column(DateTime, nullable=True)
    
    status_logistica = Column(String(50), default='Pendente') # Pendente, Em separação, Enviado, Entregue
    valor_frete = Column(Numeric(10, 2), default=0.00)
    
    pedidos = relationship("PedidoVenda", back_populates="entrega")

    historico_status = relationship(
        "EntregaStatusHistorico",
        back_populates="entrega",
        order_by="EntregaStatusHistorico.data_hora.desc()",
        cascade="all, delete-orphan"
    )


class EntregaStatusHistorico(Base):
    """
    Registro de auditoria: cada linha representa uma mudança de status de uma entrega,
    guardando obrigatoriamente o usuário responsável, quando, e de/para qual status.
    """
    __tablename__ = 'entrega_status_historico'

    id_historico = Column(Integer, primary_key=True, autoincrement=True)
    id_entrega = Column(Integer, ForeignKey('entrega.id_entrega'), nullable=False)

    # Rastreabilidade obrigatória integrada com a tabela de usuários
    id_usuario = Column(Integer, ForeignKey('usuario.id_usuario'), nullable=False)       
    nome_usuario = Column(String(150), nullable=False)  

    status_anterior = Column(String(50), nullable=True)
    status_novo = Column(String(50), nullable=False)
    data_hora = Column(DateTime, default=datetime.now, nullable=False)

    entrega = relationship("Entrega", back_populates="historico_status")
    
    # Relacionamento opcional com o model Usuario para consultas futuras se necessário
    usuario = relationship("Usuario")