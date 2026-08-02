from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database.models.base import Base


class CentroProducao(Base):
    __tablename__ = 'centro_producao'

    id_centro_producao = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(150), nullable=False)
    descricao = Column(String(255), nullable=True)
    ativo = Column(String(1), default='S')

    ordens = relationship("OrdemProducao", back_populates="centro")


class OrdemProducao(Base):
    __tablename__ = 'ordem_producao'

    id_ordem_producao = Column(Integer, primary_key=True, autoincrement=True)
    id_centro_producao = Column(Integer, ForeignKey('centro_producao.id_centro_producao'), nullable=False)
    id_item_produto = Column(Integer, ForeignKey('item.id_item'), nullable=False)
    id_usuario = Column(Integer, nullable=False)

    quantidade_planejada = Column(Numeric(10, 2), nullable=False)
    quantidade_produzida = Column(Numeric(10, 2), default=0.00)
    status_ordem = Column(String(50), default='Criado')  # Criado, Em Producao, Finalizado, Cancelado

    data_criacao = Column(DateTime, default=datetime.utcnow)
    data_inicio = Column(DateTime, nullable=True)
    data_finalizacao = Column(DateTime, nullable=True)

    centro = relationship("CentroProducao", back_populates="ordens")
    produto = relationship("Item", back_populates="ordens_producao")
    consumos = relationship("ConsumoProducao", back_populates="ordem", cascade="all, delete-orphan")


class ConsumoProducao(Base):
    __tablename__ = 'consumo_producao'

    id_consumo = Column(Integer, primary_key=True, autoincrement=True)
    id_ordem_producao = Column(Integer, ForeignKey('ordem_producao.id_ordem_producao', ondelete="CASCADE"), nullable=False)
    id_item_insumo = Column(Integer, ForeignKey('item.id_item'), nullable=False)

    quantidade = Column(Numeric(10, 2), nullable=False)
    tipo_registro = Column(String(20), nullable=False)  # CONSUMO, PERDA
    data_registro = Column(DateTime, default=datetime.utcnow)

    ordem = relationship("OrdemProducao", back_populates="consumos")
    insumo = relationship("Item", back_populates="consumos_producao")
