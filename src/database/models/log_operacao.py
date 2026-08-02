from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from src.database.models.base import Base


class LogOperacao(Base):
    __tablename__ = 'log_operacao'

    id_log = Column(Integer, primary_key=True, autoincrement=True)
    tipo_operacao = Column(String(50), nullable=False)  # COMPRA, VENDA, PRODUCAO, etc.
    origem = Column(String(50), nullable=False)  # compra, venda, producao, ajuste
    id_referencia = Column(Integer, nullable=False)
    descricao = Column(String(500), nullable=False)
    id_usuario = Column(Integer, nullable=False)
    data_hora = Column(DateTime, default=datetime.utcnow)
