from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from src.database.models.base import Base


class CentroProducao(Base):
    __tablename__ = 'centro_producao'

    id_centro_producao = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(150), nullable=False)
    descricao = Column(String(255), nullable=True)
    ativo = Column(String(1), default='S')

    ordens = relationship("OrdemProducao", back_populates="centro")


class FichaTecnica(Base):
    __tablename__ = "ficha_tecnica"

    id_ficha_tecnica = Column(Integer, primary_key=True, autoincrement=True)
    id_item_produto = Column(Integer, ForeignKey("item.id_item"), nullable=False, unique=True)
    descricao = Column(String(255), nullable=True)
    ativo = Column(String(1), nullable=False, default="S")
    data_criacao = Column(DateTime, nullable=False, default=datetime.utcnow)
    data_atualizacao = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    produto = relationship("Item", back_populates="ficha_tecnica", foreign_keys=[id_item_produto])
    componentes = relationship(
        "ItemFichaTecnica",
        back_populates="ficha_tecnica",
        cascade="all, delete-orphan",
    )


class ItemFichaTecnica(Base):
    __tablename__ = "item_ficha_tecnica"

    id_item_ficha = Column(Integer, primary_key=True, autoincrement=True)
    id_ficha_tecnica = Column(
        Integer,
        ForeignKey("ficha_tecnica.id_ficha_tecnica", ondelete="CASCADE"),
        nullable=False,
    )
    id_item_insumo = Column(Integer, ForeignKey("item.id_item"), nullable=False)
    quantidade_por_unidade = Column(Numeric(12, 4), nullable=False)

    __table_args__ = (
        UniqueConstraint("id_ficha_tecnica", "id_item_insumo", name="uq_ficha_insumo"),
    )

    ficha_tecnica = relationship("FichaTecnica", back_populates="componentes")
    insumo = relationship("Item", back_populates="fichas_componente", foreign_keys=[id_item_insumo])


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
    reservas = relationship("ReservaMaterial", back_populates="ordem", cascade="all, delete-orphan")


class ReservaMaterial(Base):
    __tablename__ = "reserva_material"

    id_reserva = Column(Integer, primary_key=True, autoincrement=True)
    id_ordem_producao = Column(
        Integer,
        ForeignKey("ordem_producao.id_ordem_producao", ondelete="CASCADE"),
        nullable=False,
    )
    id_item_insumo = Column(Integer, ForeignKey("item.id_item"), nullable=False)
    quantidade_reservada = Column(Numeric(12, 4), nullable=False)
    quantidade_consumida = Column(Numeric(12, 4), nullable=False, default=0)
    status_reserva = Column(String(20), nullable=False, default="RESERVADA")
    data_reserva = Column(DateTime, nullable=False, default=datetime.utcnow)
    data_atualizacao = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("id_ordem_producao", "id_item_insumo", name="uq_reserva_ordem_insumo"),
    )

    ordem = relationship("OrdemProducao", back_populates="reservas")
    insumo = relationship("Item", back_populates="reservas_producao")


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
