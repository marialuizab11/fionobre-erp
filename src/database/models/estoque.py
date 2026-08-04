from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from src.database.models.base import Base


class LocalizacaoEstoque(Base):
    """
    Define os locais físicos de armazenamento (ex: Armazém A, Prateleira 2).
    """
    __tablename__ = 'localizacao_estoque'

    id_localizacao = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), nullable=False, unique=True)
    descricao = Column(String(255), nullable=True)
    ativo = Column(String(1), default='S')

    estoques = relationship("EstoqueLocalizacao", back_populates="localizacao")
    itens_inventario = relationship("ItemInventario", back_populates="localizacao")


class EstoqueLocalizacao(Base):
    """
    Tabela associativa que guarda o saldo específico de um item em uma localização.
    """
    __tablename__ = 'estoque_localizacao'

    id_estoque_local = Column(Integer, primary_key=True, autoincrement=True)
    id_item = Column(Integer, ForeignKey('item.id_item'), nullable=False)
    id_localizacao = Column(Integer, ForeignKey('localizacao_estoque.id_localizacao'), nullable=False)
    quantidade = Column(Numeric(12, 4), default=0.00, nullable=False)

    __table_args__ = (
        UniqueConstraint("id_item", "id_localizacao", name="uq_estoque_item_localizacao"),
    )

    item = relationship("Item")
    localizacao = relationship("LocalizacaoEstoque", back_populates="estoques")


class InventarioFisico(Base):
    """
    Cabeçalho de um processo de contagem física (Inventário).
    """
    __tablename__ = 'inventario_fisico'

    id_inventario = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String(20), default='ABERTO')  # Status: ABERTO, CONCLUIDO, CANCELADO
    id_usuario = Column(Integer, nullable=False)
    data_inicio = Column(DateTime, default=datetime.utcnow, nullable=False)
    data_conclusao = Column(DateTime, nullable=True)
    observacoes = Column(String(255), nullable=True)

    itens = relationship("ItemInventario", back_populates="inventario", cascade="all, delete-orphan")


class ItemInventario(Base):
    """
    Linhas do inventário, comparando o que há no sistema com o que foi contado fisicamente.
    """
    __tablename__ = 'item_inventario'

    id_item_inventario = Column(Integer, primary_key=True, autoincrement=True)
    id_inventario = Column(Integer, ForeignKey('inventario_fisico.id_inventario', ondelete="CASCADE"), nullable=False)
    id_item = Column(Integer, ForeignKey('item.id_item'), nullable=False)
    id_localizacao = Column(Integer, ForeignKey('localizacao_estoque.id_localizacao'), nullable=False)
    
    quantidade_sistema = Column(Numeric(12, 4), nullable=False)
    quantidade_contada = Column(Numeric(12, 4), nullable=True)
    diferenca = Column(Numeric(12, 4), nullable=True)
    motivo_ajuste = Column(String(255), nullable=True)

    inventario = relationship("InventarioFisico", back_populates="itens")
    item = relationship("Item")
    localizacao = relationship("LocalizacaoEstoque", back_populates="itens_inventario")