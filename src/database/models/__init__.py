from src.database.models.base import Base
from src.database.models.cadastros import Cliente, Item
from src.database.models.vendas import PedidoVenda, ItemVenda
from src.database.models.compras import Fornecedor, ItemCompra, NecessidadeCompra, PedidoCompra
from src.database.models.producao import (
    AlocacaoCapacidadeProducao,
    CapacidadeCentroProducao,
    CentroProducao,
    ConsumoProducao,
    FichaTecnica,
    InspecaoQualidade,
    ItemFichaTecnica,
    OperacaoRoteiroProducao,
    OrdemProducao,
    OrdemOperacaoProducao,
    PlanejamentoOrdemProducao,
    ReservaMaterial,
    RoteiroProducao,
)
from src.database.models.logistica import (
    ComprovanteEntrega,
    DevolucaoLogistica,
    Entrega,
    EventoRastreamentoEntrega,
    ItemDevolucaoLogistica,
    ParadaRotaEntrega,
    ReferenciaRastreamentoEntrega,
    RotaEntrega,
    Veiculo,
)
from src.database.models.core import MovimentacaoEstoque
from src.database.models.financeiro import LancamentoFinanceiro
from src.database.models.usuarios import LogOperacao, Perfil, Permissao, Usuario

__all__ = [
    "Base",
    "Cliente",
    "Item",
    "PedidoVenda",
    "ItemVenda",
    "Fornecedor",
    "PedidoCompra",
    "ItemCompra",
    "NecessidadeCompra",
    "CentroProducao",
    "OrdemProducao",
    "ConsumoProducao",
    "FichaTecnica",
    "ItemFichaTecnica",
    "ReservaMaterial",
    "CapacidadeCentroProducao",
    "RoteiroProducao",
    "OperacaoRoteiroProducao",
    "PlanejamentoOrdemProducao",
    "OrdemOperacaoProducao",
    "AlocacaoCapacidadeProducao",
    "InspecaoQualidade",
    "Entrega",
    "ReferenciaRastreamentoEntrega",
    "EventoRastreamentoEntrega",
    "Veiculo",
    "RotaEntrega",
    "ParadaRotaEntrega",
    "ComprovanteEntrega",
    "DevolucaoLogistica",
    "ItemDevolucaoLogistica",
    "MovimentacaoEstoque",
    "LancamentoFinanceiro",
    "Usuario",
    "Perfil",
    "Permissao",
    "LogOperacao",
]
