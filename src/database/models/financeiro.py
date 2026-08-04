from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.database.models.base import Base


class LancamentoFinanceiro(Base):
    __tablename__ = "lancamento_financeiro"

    id_lancamento = Column(Integer, primary_key=True, autoincrement=True)
    id_pedido_venda = Column(
        Integer, ForeignKey("pedido_venda.id_pedido_venda"), nullable=True
    )
    id_pedido_compra = Column(
        Integer, ForeignKey("pedido_compra.id_pedido_compra"), nullable=True
    )
    valor = Column(Numeric(10, 2), nullable=False)
    data_vencimento = Column(DateTime, nullable=False)
    data_pagamento = Column(DateTime, nullable=True)
    tipo_lancamento = Column(String(50), nullable=False)
    origem_lancamento = Column(String(50), nullable=False)
    status_pagamento = Column(String(50), default="Pendente")

    pedido_venda = relationship("PedidoVenda", back_populates="lancamentos")
    pedido_compra = relationship("PedidoCompra", back_populates="lancamentos")
    detalhe = relationship(
        "DetalheLancamentoFinanceiro",
        back_populates="lancamento",
        uselist=False,
        cascade="all, delete-orphan",
    )
    movimento_extrato = relationship(
        "MovimentoExtratoBancario",
        back_populates="lancamento",
        uselist=False,
    )


class DetalheLancamentoFinanceiro(Base):
    """Informações adicionais sem alterar lançamentos legados do ERP."""

    __tablename__ = "detalhe_lancamento_financeiro"

    id_lancamento = Column(
        Integer,
        ForeignKey("lancamento_financeiro.id_lancamento", ondelete="CASCADE"),
        primary_key=True,
    )
    descricao = Column(String(255), nullable=False)
    categoria = Column(String(100), nullable=False)
    observacao = Column(Text, nullable=True)
    id_usuario_criacao = Column(
        Integer, ForeignKey("usuario.id_usuario"), nullable=True
    )
    data_criacao = Column(DateTime, nullable=False, default=datetime.utcnow)

    lancamento = relationship("LancamentoFinanceiro", back_populates="detalhe")
    usuario_criacao = relationship("Usuario")


class MovimentoExtratoBancario(Base):
    """Linha de extrato importada ou digitada para conciliação bancária."""

    __tablename__ = "movimento_extrato_bancario"

    id_movimento = Column(Integer, primary_key=True, autoincrement=True)
    data_movimento = Column(DateTime, nullable=False)
    descricao = Column(String(255), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    referencia = Column(String(150), nullable=True, index=True)
    id_lancamento = Column(
        Integer,
        ForeignKey("lancamento_financeiro.id_lancamento"),
        nullable=True,
        unique=True,
    )
    data_conciliacao = Column(DateTime, nullable=True)
    id_usuario_conciliacao = Column(
        Integer, ForeignKey("usuario.id_usuario"), nullable=True
    )
    data_importacao = Column(DateTime, nullable=False, default=datetime.utcnow)

    lancamento = relationship(
        "LancamentoFinanceiro", back_populates="movimento_extrato"
    )
    usuario_conciliacao = relationship("Usuario")
