from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from src.database.models.base import Base


class Fornecedor(Base):
    __tablename__ = 'fornecedor'

    id_fornecedor = Column(Integer, primary_key=True, autoincrement=True)
    razao_social = Column(String(255), nullable=False)
    cnpj_cpf = Column(String(20), unique=True, nullable=False)
    email = Column(String(100), nullable=True)
    telefone = Column(String(20), nullable=True)

    cep = Column(String(10), nullable=True)
    rua = Column(String(150), nullable=True)
    numero = Column(String(20), nullable=True)
    bairro = Column(String(100), nullable=True)
    cidade = Column(String(100), nullable=True)
    uf = Column(String(2), nullable=True)

    pedidos = relationship("PedidoCompra", back_populates="fornecedor")


class PedidoCompra(Base):
    __tablename__ = 'pedido_compra'

    id_pedido_compra = Column(Integer, primary_key=True, autoincrement=True)
    id_fornecedor = Column(Integer, ForeignKey('fornecedor.id_fornecedor'), nullable=False)
    id_usuario = Column(Integer, nullable=False)

    data_pedido = Column(DateTime, default=datetime.utcnow)
    status_compra = Column(String(50), default='Criado')  # Criado, Confirmado, Recebido, Cancelado
    valor_total_pedido = Column(Numeric(10, 2), default=0.00)
    justificativa_cancelamento = Column(String, nullable=True)

    fornecedor = relationship("Fornecedor", back_populates="pedidos")
    itens = relationship("ItemCompra", back_populates="pedido", cascade="all, delete-orphan")
    lancamentos = relationship("LancamentoFinanceiro", back_populates="pedido_compra")


class ItemCompra(Base):
    __tablename__ = 'item_compra'

    id_pedido_compra = Column(Integer, ForeignKey('pedido_compra.id_pedido_compra', ondelete="CASCADE"))
    id_item = Column(Integer, ForeignKey('item.id_item'), nullable=False)

    quantidade_comprada = Column(Numeric(10, 2), nullable=False)
    custo_unitario = Column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint('id_pedido_compra', 'id_item'),
    )

    pedido = relationship("PedidoCompra", back_populates="itens")
    item = relationship("Item", back_populates="itens_comprados")
