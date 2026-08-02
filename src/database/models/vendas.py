from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from src.database.models.base import Base

class PedidoVenda(Base):
    __tablename__ = 'pedido_venda'
    
    id_pedido_venda = Column(Integer, primary_key=True, autoincrement=True)
    id_cliente = Column(Integer, ForeignKey('cliente.id_cliente'), nullable=False)
    id_usuario = Column(Integer, ForeignKey('usuario.id_usuario'), nullable=False)
    id_entrega = Column(Integer, ForeignKey('entrega.id_entrega'), nullable=True)
    
    data_venda = Column(DateTime, default=datetime.utcnow)
    status_venda = Column(String(50), default='Criado')  
    valor_total_pedido = Column(Numeric(10, 2), default=0.00)
    justificativa_cancelamento = Column(String, nullable=True)
    
    cliente = relationship("Cliente", back_populates="pedidos")
    usuario = relationship("Usuario", back_populates="pedidos_venda")
    entrega = relationship("Entrega", back_populates="pedidos")
    
    itens = relationship("ItemVenda", back_populates="pedido", cascade="all, delete-orphan")
    lancamentos = relationship("LancamentoFinanceiro", back_populates="pedido_venda", cascade="all, delete-orphan")
    
    historico_status = relationship(
        "PedidoVendaHistorico", 
        back_populates="pedido", 
        order_by="PedidoVendaHistorico.data_hora.desc()",
        cascade="all, delete-orphan"
    )


class ItemVenda(Base):
    __tablename__ = 'item_venda'
    
    id_pedido_venda = Column(Integer, ForeignKey('pedido_venda.id_pedido_venda', ondelete="CASCADE"))
    id_item = Column(Integer, ForeignKey('item.id_item'), nullable=False)
    
    quantidade_vendida = Column(Numeric(10, 2), nullable=False)
    valor_unitario = Column(Numeric(10, 2), nullable=False)
    
    __table_args__ = (
        PrimaryKeyConstraint('id_pedido_venda', 'id_item'),
    )
    
    pedido = relationship("PedidoVenda", back_populates="itens")
    item = relationship("Item", back_populates="itens_vendidos")
    
class PedidoVendaHistorico(Base):
    """
    Registro de auditoria: rastreia quando o pedido foi criado, 
    cancelado ou concluído, registrando o responsável e a justificativa.
    """
    __tablename__ = 'pedido_venda_historico'
    
    id_historico = Column(Integer, primary_key=True, autoincrement=True)
    id_pedido_venda = Column(Integer, ForeignKey('pedido_venda.id_pedido_venda'), nullable=False)
    
    id_usuario = Column(Integer, nullable=True)
    nome_usuario = Column(String(150), nullable=True)
    
    status_anterior = Column(String(50), nullable=True)
    status_novo = Column(String(50), nullable=False)
    justificativa = Column(String(255), nullable=True)
    data_hora = Column(DateTime, default=datetime.now, nullable=False)
    
    pedido = relationship("PedidoVenda", back_populates="historico_status")