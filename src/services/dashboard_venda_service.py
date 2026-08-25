from datetime import datetime
from decimal import Decimal
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from src.database.models.cadastros import Item
from src.database.models.vendas import PedidoVenda, ItemVenda, PedidoVendaHistorico


def obter_kpis_comerciais(db: Session, data_inicio: datetime, data_fim: datetime) -> dict:
    """Calcula Faturamento Bruto, Ticket Médio e Taxa de Conversão."""
    
    # 1. Faturamento e Ticket Médio
    query_vendas = db.query(
        func.sum(PedidoVenda.valor_total_pedido).label("faturamento_bruto"),
        func.count(PedidoVenda.id_pedido_venda).label("total_pedidos")
    ).filter(
        PedidoVenda.status_venda.in_(["Confirmado", "Concluído"]),
        PedidoVenda.data_venda >= data_inicio,
        PedidoVenda.data_venda <= data_fim
    ).first()

    faturamento = float(query_vendas.faturamento_bruto or 0.0)
    total_pedidos = int(query_vendas.total_pedidos or 0)
    ticket_medio = faturamento / total_pedidos if total_pedidos > 0 else 0.0

    # 2. Taxa de Conversão de Orçamentos
    # Conta quantos orçamentos foram gerados no período
    orcamentos_gerados = db.query(func.count(PedidoVendaHistorico.id_historico)).filter(
        PedidoVendaHistorico.status_novo == "Orcamento",
        PedidoVendaHistorico.data_hora >= data_inicio,
        PedidoVendaHistorico.data_hora <= data_fim
    ).scalar() or 0

    # Conta quantos foram convertidos (status_anterior="Orcamento" para status_novo="Confirmado")
    orcamentos_convertidos = db.query(func.count(PedidoVendaHistorico.id_historico)).filter(
        PedidoVendaHistorico.status_anterior == "Orcamento",
        PedidoVendaHistorico.status_novo == "Confirmado",
        PedidoVendaHistorico.data_hora >= data_inicio,
        PedidoVendaHistorico.data_hora <= data_fim
    ).scalar() or 0

    taxa_conversao = (orcamentos_convertidos / orcamentos_gerados * 100) if orcamentos_gerados > 0 else 0.0

    return {
        "faturamento_bruto": faturamento,
        "ticket_medio": ticket_medio,
        "taxa_conversao": taxa_conversao,
        "orcamentos_gerados": orcamentos_gerados,
        "orcamentos_convertidos": orcamentos_convertidos
    }


def obter_faturamento_por_periodo(db: Session, data_inicio: datetime, data_fim: datetime):
    """Agrupa o faturamento por data para o gráfico de linhas."""
    resultados = db.query(
        func.date(PedidoVenda.data_venda).label("data"),
        func.sum(PedidoVenda.valor_total_pedido).label("faturamento")
    ).filter(
        PedidoVenda.status_venda.in_(["Confirmado", "Concluído"]),
        PedidoVenda.data_venda >= data_inicio,
        PedidoVenda.data_venda <= data_fim
    ).group_by(
        func.date(PedidoVenda.data_venda)
    ).order_by(
        func.date(PedidoVenda.data_venda)
    ).all()

    return [{"data": str(r.data), "faturamento": float(r.faturamento or 0)} for r in resultados]


def obter_top_5_produtos(db: Session, data_inicio: datetime, data_fim: datetime):
    """Busca os 5 produtos mais vendidos (em quantidade) no período."""
    resultados = db.query(
        Item.descricao,
        func.sum(ItemVenda.quantidade_vendida).label("quantidade_total"),
        func.sum(ItemVenda.quantidade_vendida * ItemVenda.valor_unitario).label("receita_total")
    ).join(
        ItemVenda, Item.id_item == ItemVenda.id_item
    ).join(
        PedidoVenda, ItemVenda.id_pedido_venda == PedidoVenda.id_pedido_venda
    ).filter(
        PedidoVenda.status_venda.in_(["Confirmado", "Concluído"]),
        PedidoVenda.data_venda >= data_inicio,
        PedidoVenda.data_venda <= data_fim
    ).group_by(
        Item.id_item, Item.descricao
    ).order_by(
        desc("quantidade_total")
    ).limit(5).all()

    return [
        {
            "produto": r.descricao, 
            "quantidade": float(r.quantidade_total or 0), 
            "receita": float(r.receita_total or 0)
        } for r in resultados
    ]