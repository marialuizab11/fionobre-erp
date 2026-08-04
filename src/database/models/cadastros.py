from sqlalchemy import Column, Integer, String, Numeric
from sqlalchemy.orm import relationship
from src.database.models.base import Base

class Cliente(Base):
    __tablename__ = 'cliente'
    
    id_cliente = Column(Integer, primary_key=True, autoincrement=True)
    razao_social = Column(String(255), nullable=False)
    cnpj_cpf = Column(String(20), unique=True, nullable=False)
    email = Column(String(100), nullable=True)
    telefone = Column(String(20), nullable=True)
    
    # Endereço desmembrado conforme as elipses do MER
    cep = Column(String(10), nullable=True)
    rua = Column(String(150), nullable=True)
    numero = Column(String(20), nullable=True)
    bairro = Column(String(100), nullable=True)
    cidade = Column(String(100), nullable=True)
    uf = Column(String(2), nullable=True)
    
    # Relacionamento com Vendas (Mapeamento ORM)
    pedidos = relationship("PedidoVenda", back_populates="cliente")


class Item(Base):
    __tablename__ = 'item'
    
    id_item = Column(Integer, primary_key=True, autoincrement=True)
    descricao = Column(String(255), nullable=False)
    saldo_estoque = Column(Numeric(10, 2), default=0.00)
    estoque_minimo = Column(Numeric(10, 2), default=0.00)
    preco_venda = Column(Numeric(10, 2), default=0.00)
    custo_medio = Column(Numeric(10, 2), default=0.00)
    unidade_medida = Column(String(20), nullable=False)
    tipo_item = Column(String(50), nullable=False)
    
    # Relacionamentos
    itens_vendidos = relationship("ItemVenda", back_populates="item")
    itens_comprados = relationship("ItemCompra", back_populates="item")
    movimentacoes = relationship("MovimentacaoEstoque", back_populates="item")
    ordens_producao = relationship("OrdemProducao", back_populates="produto")
    consumos_producao = relationship("ConsumoProducao", back_populates="insumo")
    ficha_tecnica = relationship(
        "FichaTecnica", back_populates="produto", uselist=False,
        foreign_keys="FichaTecnica.id_item_produto",
    )
    fichas_componente = relationship(
        "ItemFichaTecnica", back_populates="insumo",
        foreign_keys="ItemFichaTecnica.id_item_insumo",
    )
    reservas_producao = relationship("ReservaMaterial", back_populates="insumo")
