from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import relationship

from src.database.models.base import Base


perfil_permissao = Table(
    "perfil_permissao",
    Base.metadata,
    Column("id_perfil", ForeignKey("perfil.id_perfil", ondelete="CASCADE"), primary_key=True),
    Column(
        "id_permissao",
        ForeignKey("permissao.id_permissao", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Perfil(Base):
    __tablename__ = "perfil"

    id_perfil = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(50), unique=True, nullable=False)
    descricao = Column(String(255), nullable=True)

    permissoes = relationship(
        "Permissao",
        secondary=perfil_permissao,
        back_populates="perfis",
    )
    usuarios = relationship("Usuario", back_populates="perfil")


class Permissao(Base):
    __tablename__ = "permissao"

    id_permissao = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String(100), unique=True, nullable=False)
    descricao = Column(String(255), nullable=False)

    perfis = relationship(
        "Perfil",
        secondary=perfil_permissao,
        back_populates="permissoes",
    )


class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario = Column(Integer, primary_key=True, autoincrement=True)
    google_sub = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    nome = Column(String(255), nullable=False)
    foto_url = Column(String(1000), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    id_perfil = Column(Integer, ForeignKey("perfil.id_perfil"), nullable=False)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    ultimo_login_em = Column(DateTime, nullable=True)

    perfil = relationship("Perfil", back_populates="usuarios")
    logs = relationship("LogOperacao", back_populates="usuario")
    pedidos_venda = relationship("PedidoVenda", back_populates="usuario")
    movimentacoes_estoque = relationship("MovimentacaoEstoque", back_populates="usuario")


class LogOperacao(Base):
    __tablename__ = "log_operacao"

    id_log = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario"), nullable=False)
    modulo = Column(String(50), nullable=False)
    acao = Column(String(100), nullable=False)
    entidade = Column(String(100), nullable=True)
    id_registro = Column(String(100), nullable=True)
    detalhes = Column(Text, nullable=True)
    data_hora = Column(DateTime, nullable=False, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="logs")
