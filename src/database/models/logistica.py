from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    desc
)
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
        order_by=lambda: desc(EntregaStatusHistorico.data_hora),
        cascade="all, delete-orphan"
    )
    rastreamento = relationship(
        "ReferenciaRastreamentoEntrega",
        back_populates="entrega",
        uselist=False,
        cascade="all, delete-orphan",
    )
    eventos_rastreamento = relationship(
        "EventoRastreamentoEntrega",
        back_populates="entrega",
        order_by="EventoRastreamentoEntrega.data_evento.desc()",
        cascade="all, delete-orphan",
    )
    paradas_rota = relationship("ParadaRotaEntrega", back_populates="entrega")
    comprovante = relationship(
        "ComprovanteEntrega",
        back_populates="entrega",
        uselist=False,
        cascade="all, delete-orphan",
    )
    devolucoes = relationship(
        "DevolucaoLogistica",
        back_populates="entrega",
        order_by="DevolucaoLogistica.data_solicitacao.desc()",
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


class ReferenciaRastreamentoEntrega(Base):
    __tablename__ = "referencia_rastreamento_entrega"

    id_entrega = Column(
        Integer,
        ForeignKey("entrega.id_entrega", ondelete="CASCADE"),
        primary_key=True,
    )
    transportadora = Column(String(150), nullable=True)
    codigo_rastreio = Column(String(150), nullable=False)
    url_rastreamento = Column(String(1000), nullable=True)
    data_atualizacao = Column(DateTime, nullable=False, default=datetime.utcnow)

    entrega = relationship("Entrega", back_populates="rastreamento")


class EventoRastreamentoEntrega(Base):
    __tablename__ = "evento_rastreamento_entrega"

    id_evento = Column(Integer, primary_key=True, autoincrement=True)
    id_entrega = Column(
        Integer, ForeignKey("entrega.id_entrega", ondelete="CASCADE"), nullable=False
    )
    status = Column(String(50), nullable=False)
    descricao = Column(String(255), nullable=True)
    localizacao = Column(String(255), nullable=True)
    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario"), nullable=True)
    data_evento = Column(DateTime, nullable=False, default=datetime.utcnow)

    entrega = relationship("Entrega", back_populates="eventos_rastreamento")
    usuario = relationship("Usuario")


class Veiculo(Base):
    __tablename__ = "veiculo"

    id_veiculo = Column(Integer, primary_key=True, autoincrement=True)
    placa = Column(String(10), nullable=False, unique=True)
    descricao = Column(String(150), nullable=False)
    motorista = Column(String(150), nullable=True)
    capacidade_kg = Column(Numeric(10, 2), nullable=False)
    ativo = Column(String(1), nullable=False, default="S")

    rotas = relationship("RotaEntrega", back_populates="veiculo")


class RotaEntrega(Base):
    __tablename__ = "rota_entrega"

    id_rota = Column(Integer, primary_key=True, autoincrement=True)
    descricao = Column(String(200), nullable=False)
    data_planejada = Column(DateTime, nullable=False)
    data_inicio = Column(DateTime, nullable=True)
    data_finalizacao = Column(DateTime, nullable=True)
    status_rota = Column(String(30), nullable=False, default="PLANEJADA")
    id_veiculo = Column(Integer, ForeignKey("veiculo.id_veiculo"), nullable=False)
    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario"), nullable=False)

    veiculo = relationship("Veiculo", back_populates="rotas")
    usuario = relationship("Usuario")
    paradas = relationship(
        "ParadaRotaEntrega",
        back_populates="rota",
        order_by="ParadaRotaEntrega.sequencia",
        cascade="all, delete-orphan",
    )


class ParadaRotaEntrega(Base):
    __tablename__ = "parada_rota_entrega"

    id_parada = Column(Integer, primary_key=True, autoincrement=True)
    id_rota = Column(
        Integer, ForeignKey("rota_entrega.id_rota", ondelete="CASCADE"), nullable=False
    )
    id_entrega = Column(Integer, ForeignKey("entrega.id_entrega"), nullable=False)
    sequencia = Column(Integer, nullable=False)
    peso_estimado_kg = Column(Numeric(10, 2), nullable=False, default=0)
    status_parada = Column(String(30), nullable=False, default="PENDENTE")
    observacao = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("id_rota", "sequencia", name="uq_rota_sequencia"),
        UniqueConstraint("id_rota", "id_entrega", name="uq_rota_entrega"),
    )

    rota = relationship("RotaEntrega", back_populates="paradas")
    entrega = relationship("Entrega", back_populates="paradas_rota")


class ComprovanteEntrega(Base):
    __tablename__ = "comprovante_entrega"

    id_comprovante = Column(Integer, primary_key=True, autoincrement=True)
    id_entrega = Column(
        Integer, ForeignKey("entrega.id_entrega"), nullable=False, unique=True
    )
    nome_recebedor = Column(String(150), nullable=False)
    documento_recebedor = Column(String(30), nullable=True)
    assinatura_recebedor = Column(String(255), nullable=False)
    nome_arquivo = Column(String(255), nullable=True)
    tipo_arquivo = Column(String(100), nullable=True)
    conteudo_arquivo = Column(LargeBinary, nullable=True)
    hash_arquivo = Column(String(64), nullable=True)
    observacao = Column(Text, nullable=True)
    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario"), nullable=False)
    data_recebimento = Column(DateTime, nullable=False, default=datetime.utcnow)

    entrega = relationship("Entrega", back_populates="comprovante")
    usuario = relationship("Usuario")


class DevolucaoLogistica(Base):
    __tablename__ = "devolucao_logistica"

    id_devolucao = Column(Integer, primary_key=True, autoincrement=True)
    id_entrega = Column(Integer, ForeignKey("entrega.id_entrega"), nullable=False)
    motivo = Column(String(255), nullable=False)
    status_devolucao = Column(String(30), nullable=False, default="SOLICITADA")
    observacao = Column(Text, nullable=True)
    id_usuario_solicitacao = Column(
        Integer, ForeignKey("usuario.id_usuario"), nullable=False
    )
    id_usuario_recebimento = Column(
        Integer, ForeignKey("usuario.id_usuario"), nullable=True
    )
    data_solicitacao = Column(DateTime, nullable=False, default=datetime.utcnow)
    data_recebimento = Column(DateTime, nullable=True)

    entrega = relationship("Entrega", back_populates="devolucoes")
    usuario_solicitacao = relationship("Usuario", foreign_keys=[id_usuario_solicitacao])
    usuario_recebimento = relationship("Usuario", foreign_keys=[id_usuario_recebimento])
    itens = relationship(
        "ItemDevolucaoLogistica",
        back_populates="devolucao",
        cascade="all, delete-orphan",
    )


class ItemDevolucaoLogistica(Base):
    __tablename__ = "item_devolucao_logistica"

    id_item_devolucao = Column(Integer, primary_key=True, autoincrement=True)
    id_devolucao = Column(
        Integer,
        ForeignKey("devolucao_logistica.id_devolucao", ondelete="CASCADE"),
        nullable=False,
    )
    id_item = Column(Integer, ForeignKey("item.id_item"), nullable=False)
    quantidade = Column(Numeric(10, 2), nullable=False)
    condicao_item = Column(String(30), nullable=False, default="INTEGRO")
    reintegrar_estoque = Column(Boolean, nullable=False, default=True)

    devolucao = relationship("DevolucaoLogistica", back_populates="itens")
    item = relationship("Item")