from datetime import datetime
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from src.database.models.base import Base


class CentroProducao(Base):
    __tablename__ = 'centro_producao'

    id_centro_producao = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(150), nullable=False)
    descricao = Column(String(255), nullable=True)
    ativo = Column(String(1), default='S')

    ordens = relationship("OrdemProducao", back_populates="centro")
    capacidade = relationship(
        "CapacidadeCentroProducao",
        back_populates="centro",
        uselist=False,
        cascade="all, delete-orphan",
    )
    operacoes_roteiro = relationship("OperacaoRoteiroProducao", back_populates="centro")
    operacoes_planejadas = relationship("OrdemOperacaoProducao", back_populates="centro")


class FichaTecnica(Base):
    __tablename__ = "ficha_tecnica"

    id_ficha_tecnica = Column(Integer, primary_key=True, autoincrement=True)
    id_item_produto = Column(Integer, ForeignKey("item.id_item"), nullable=False, unique=True)
    descricao = Column(String(255), nullable=True)
    ativo = Column(String(1), nullable=False, default="S")
    data_criacao = Column(DateTime, nullable=False, default=datetime.now)
    data_atualizacao = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.utcnow)

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
    planejamento = relationship(
        "PlanejamentoOrdemProducao",
        back_populates="ordem",
        uselist=False,
        cascade="all, delete-orphan",
    )
    operacoes = relationship(
        "OrdemOperacaoProducao",
        back_populates="ordem",
        order_by="OrdemOperacaoProducao.sequencia",
        cascade="all, delete-orphan",
    )
    inspecoes_qualidade = relationship(
        "InspecaoQualidade",
        back_populates="ordem",
        order_by="InspecaoQualidade.data_inspecao.desc()",
        cascade="all, delete-orphan",
    )


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


class CapacidadeCentroProducao(Base):
    __tablename__ = "capacidade_centro_producao"

    id_centro_producao = Column(
        Integer,
        ForeignKey("centro_producao.id_centro_producao", ondelete="CASCADE"),
        primary_key=True,
    )
    horas_disponiveis_dia = Column(Numeric(8, 2), nullable=False, default=8)
    hora_inicio_expediente = Column(String(5), nullable=False, default="08:00")
    dias_uteis = Column(String(20), nullable=False, default="0,1,2,3,4")
    data_atualizacao = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    centro = relationship("CentroProducao", back_populates="capacidade")


class RoteiroProducao(Base):
    __tablename__ = "roteiro_producao"

    id_roteiro = Column(Integer, primary_key=True, autoincrement=True)
    id_item_produto = Column(
        Integer, ForeignKey("item.id_item"), nullable=False, unique=True
    )
    descricao = Column(String(255), nullable=True)
    ativo = Column(String(1), nullable=False, default="S")
    data_criacao = Column(DateTime, nullable=False, default=datetime.utcnow)
    data_atualizacao = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    produto = relationship("Item")
    operacoes = relationship(
        "OperacaoRoteiroProducao",
        back_populates="roteiro",
        order_by="OperacaoRoteiroProducao.sequencia",
        cascade="all, delete-orphan",
    )
    planejamentos = relationship("PlanejamentoOrdemProducao", back_populates="roteiro")


class OperacaoRoteiroProducao(Base):
    __tablename__ = "operacao_roteiro_producao"

    id_operacao_roteiro = Column(Integer, primary_key=True, autoincrement=True)
    id_roteiro = Column(
        Integer,
        ForeignKey("roteiro_producao.id_roteiro", ondelete="CASCADE"),
        nullable=False,
    )
    id_centro_producao = Column(
        Integer, ForeignKey("centro_producao.id_centro_producao"), nullable=False
    )
    sequencia = Column(Integer, nullable=False)
    nome_operacao = Column(String(150), nullable=False)
    recurso = Column(String(150), nullable=True)
    tempo_setup_horas = Column(Numeric(8, 2), nullable=False, default=0)
    tempo_unitario_horas = Column(Numeric(10, 4), nullable=False, default=0)
    instrucoes = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("id_roteiro", "sequencia", name="uq_roteiro_sequencia"),
    )

    roteiro = relationship("RoteiroProducao", back_populates="operacoes")
    centro = relationship("CentroProducao", back_populates="operacoes_roteiro")


class PlanejamentoOrdemProducao(Base):
    __tablename__ = "planejamento_ordem_producao"

    id_ordem_producao = Column(
        Integer,
        ForeignKey("ordem_producao.id_ordem_producao", ondelete="CASCADE"),
        primary_key=True,
    )
    id_roteiro = Column(Integer, ForeignKey("roteiro_producao.id_roteiro"), nullable=False)
    data_inicio_planejada = Column(DateTime, nullable=False)
    data_fim_planejada = Column(DateTime, nullable=False)
    carga_total_horas = Column(Numeric(10, 2), nullable=False)
    status_planejamento = Column(String(30), nullable=False, default="PLANEJADO")

    ordem = relationship("OrdemProducao", back_populates="planejamento")
    roteiro = relationship("RoteiroProducao", back_populates="planejamentos")


class OrdemOperacaoProducao(Base):
    __tablename__ = "ordem_operacao_producao"

    id_ordem_operacao = Column(Integer, primary_key=True, autoincrement=True)
    id_ordem_producao = Column(
        Integer,
        ForeignKey("ordem_producao.id_ordem_producao", ondelete="CASCADE"),
        nullable=False,
    )
    id_operacao_roteiro = Column(
        Integer, ForeignKey("operacao_roteiro_producao.id_operacao_roteiro"), nullable=True
    )
    id_centro_producao = Column(
        Integer, ForeignKey("centro_producao.id_centro_producao"), nullable=False
    )
    sequencia = Column(Integer, nullable=False)
    nome_operacao = Column(String(150), nullable=False)
    recurso = Column(String(150), nullable=True)
    carga_horas = Column(Numeric(10, 2), nullable=False)
    inicio_planejado = Column(DateTime, nullable=False)
    fim_planejado = Column(DateTime, nullable=False)
    inicio_real = Column(DateTime, nullable=True)
    fim_real = Column(DateTime, nullable=True)
    status_operacao = Column(String(30), nullable=False, default="PENDENTE")

    __table_args__ = (
        UniqueConstraint("id_ordem_producao", "sequencia", name="uq_ordem_operacao_seq"),
    )

    ordem = relationship("OrdemProducao", back_populates="operacoes")
    operacao_roteiro = relationship("OperacaoRoteiroProducao")
    centro = relationship("CentroProducao", back_populates="operacoes_planejadas")
    alocacoes = relationship(
        "AlocacaoCapacidadeProducao",
        back_populates="ordem_operacao",
        cascade="all, delete-orphan",
    )
    inspecoes = relationship("InspecaoQualidade", back_populates="ordem_operacao")


class AlocacaoCapacidadeProducao(Base):
    __tablename__ = "alocacao_capacidade_producao"

    id_alocacao = Column(Integer, primary_key=True, autoincrement=True)
    id_ordem_operacao = Column(
        Integer,
        ForeignKey("ordem_operacao_producao.id_ordem_operacao", ondelete="CASCADE"),
        nullable=False,
    )
    id_centro_producao = Column(
        Integer, ForeignKey("centro_producao.id_centro_producao"), nullable=False
    )
    data_alocacao = Column(Date, nullable=False)
    horas_alocadas = Column(Numeric(8, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint("id_ordem_operacao", "data_alocacao", name="uq_operacao_dia"),
    )

    ordem_operacao = relationship("OrdemOperacaoProducao", back_populates="alocacoes")
    centro = relationship("CentroProducao")


class InspecaoQualidade(Base):
    __tablename__ = "inspecao_qualidade"

    id_inspecao = Column(Integer, primary_key=True, autoincrement=True)
    id_ordem_producao = Column(
        Integer,
        ForeignKey("ordem_producao.id_ordem_producao", ondelete="CASCADE"),
        nullable=False,
    )
    id_ordem_operacao = Column(
        Integer, ForeignKey("ordem_operacao_producao.id_ordem_operacao"), nullable=True
    )
    etapa = Column(String(20), nullable=False)
    resultado = Column(String(20), nullable=False)
    quantidade_inspecionada = Column(Numeric(10, 2), nullable=False)
    quantidade_aprovada = Column(Numeric(10, 2), nullable=False)
    quantidade_reprovada = Column(Numeric(10, 2), nullable=False, default=0)
    observacao = Column(Text, nullable=True)
    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario"), nullable=False)
    data_inspecao = Column(DateTime, nullable=False, default=datetime.utcnow)

    ordem = relationship("OrdemProducao", back_populates="inspecoes_qualidade")
    ordem_operacao = relationship("OrdemOperacaoProducao", back_populates="inspecoes")
    usuario = relationship("Usuario")
