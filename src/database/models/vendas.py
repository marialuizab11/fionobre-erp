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
    status_venda = Column(String(50), default='Criado')  # Criado, Confirmado, Cancelado
    valor_total_pedido = Column(Numeric(10, 2), default=0.00)
    justificativa_cancelamento = Column(String, nullable=True)
    
    # Relacionamentos do ORM (Mapeamento de navegação do Peter Chen)
    cliente = relationship("Cliente", back_populates="pedidos")
    usuario = relationship("Usuario", back_populates="pedidos_venda")
    entrega = relationship("Entrega", back_populates="pedidos")
    
    # Composição (Relacionamento Fraco): Se deletar o pedido, os itens somem junto
    itens = relationship("ItemVenda", back_populates="pedido", cascade="all, delete-orphan")


class ItemVenda(Base):
    __tablename__ = 'item_venda'
    
    id_pedido_venda = Column(Integer, ForeignKey('pedido_venda.id_pedido_venda', ondelete="CASCADE"))
    id_item = Column(Integer, ForeignKey('item.id_item'), nullable=False)
    
    quantidade_vendida = Column(Numeric(10, 2), nullable=False)
    valor_unitario = Column(Numeric(10, 2), nullable=False)
    
    # Chave Primária Composta (A marca registrada da Entidade Fraca no seu MER)
    __table_args__ = (
        PrimaryKeyConstraint('id_pedido_venda', 'id_item'),
    )
    
    pedido = relationship("PedidoVenda", back_populates="itens")
    item = relationship("Item", back_populates="itens_vendidos")
