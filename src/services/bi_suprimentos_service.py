from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.models.cadastros import Item
from src.database.models.compras import ItemCompra, PedidoCompra


@dataclass(frozen=True)
class IndicadoresSuprimentos:
    valor_imobilizado: Decimal
    itens_em_ruptura: int
    custo_total_aquisicao: Decimal
    valor_por_tipo: list[dict]


ROTULOS_TIPO_ITEM = {
    "PRODUTO_ACABADO": "Produto Acabado",
    "MATERIA_PRIMA": "Matéria-Prima",
    "INSUMO": "Insumo",
}


def _inicio_do_dia(valor: date) -> datetime:
    return datetime.combine(valor, time.min)


def calcular_indicadores_suprimentos(
    db: Session,
    data_inicio: date,
    data_fim: date,
) -> IndicadoresSuprimentos:
    """Calcula os KPIs de suprimentos e estoque para o período informado."""
    if data_inicio > data_fim:
        raise ValueError("A data inicial não pode ser posterior à data final.")

    valor_item = func.coalesce(Item.saldo_estoque, 0) * func.coalesce(
        Item.custo_medio, 0
    )
    valor_imobilizado = db.query(func.coalesce(func.sum(valor_item), 0)).scalar()

    itens_em_ruptura = (
        db.query(func.count(Item.id_item))
        .filter(
            func.coalesce(Item.saldo_estoque, 0)
            < func.coalesce(Item.estoque_minimo, 0)
        )
        .scalar()
    )

    # Limite superior exclusivo inclui pedidos registrados em qualquer horário
    # do último dia selecionado.
    inicio = _inicio_do_dia(data_inicio)
    fim_exclusivo = _inicio_do_dia(data_fim + timedelta(days=1))
    custo_total_aquisicao = (
        db.query(func.coalesce(func.sum(PedidoCompra.valor_total_pedido), 0))
        .filter(
            PedidoCompra.status_compra.in_(("Confirmado", "Recebido")),
            PedidoCompra.data_pedido >= inicio,
            PedidoCompra.data_pedido < fim_exclusivo,
        )
        .scalar()
    )

    distribuicao = (
        db.query(Item.tipo_item, func.coalesce(func.sum(valor_item), 0))
        .group_by(Item.tipo_item)
        .order_by(Item.tipo_item)
        .all()
    )
    valor_por_tipo = [
        {
            "Tipo de item": ROTULOS_TIPO_ITEM.get(
                tipo, (tipo or "Não informado").replace("_", " ").title()
            ),
            "Valor em estoque": float(valor or 0),
        }
        for tipo, valor in distribuicao
        if Decimal(str(valor or 0)) > 0
    ]

    return IndicadoresSuprimentos(
        valor_imobilizado=Decimal(str(valor_imobilizado or 0)),
        itens_em_ruptura=int(itens_em_ruptura or 0),
        custo_total_aquisicao=Decimal(str(custo_total_aquisicao or 0)),
        valor_por_tipo=valor_por_tipo,
    )


def calcular_necessidades_reposicao(db: Session) -> list[dict]:
    """Sugere reposição considerando saldo, mínimo e compras ainda abertas."""
    compras_abertas = (
        db.query(
            ItemCompra.id_item.label("id_item"),
            func.sum(ItemCompra.quantidade_comprada).label("quantidade_em_compra"),
        )
        .join(
            PedidoCompra,
            PedidoCompra.id_pedido_compra == ItemCompra.id_pedido_compra,
        )
        .filter(PedidoCompra.status_compra.in_(("Criado", "Confirmado")))
        .group_by(ItemCompra.id_item)
        .subquery()
    )

    registros = (
        db.query(
            Item,
            func.coalesce(compras_abertas.c.quantidade_em_compra, 0),
        )
        .outerjoin(compras_abertas, compras_abertas.c.id_item == Item.id_item)
        .all()
    )

    necessidades = []
    for item, quantidade_em_compra in registros:
        saldo = Decimal(str(item.saldo_estoque or 0))
        minimo = Decimal(str(item.estoque_minimo or 0))
        em_compra = Decimal(str(quantidade_em_compra or 0))
        sugestao = max(minimo - saldo - em_compra, Decimal("0"))

        if sugestao > 0 and saldo <= 0:
            situacao = "Crítico"
        elif sugestao > 0:
            situacao = "Urgente"
        elif saldo < minimo:
            situacao = "Compra em andamento"
        else:
            situacao = "Normal"

        necessidades.append(
            {
                "ID": item.id_item,
                "Item": item.descricao,
                "Tipo": ROTULOS_TIPO_ITEM.get(
                    item.tipo_item,
                    (item.tipo_item or "Não informado").replace("_", " ").title(),
                ),
                "Unidade": item.unidade_medida,
                "Saldo atual": float(saldo),
                "Estoque mínimo": float(minimo),
                "Em compra": float(em_compra),
                "Sugestão de compra": float(sugestao),
                "Situação": situacao,
            }
        )

    prioridade = {"Crítico": 0, "Urgente": 1, "Compra em andamento": 2, "Normal": 3}
    return sorted(
        necessidades,
        key=lambda registro: (
            prioridade[registro["Situação"]],
            -registro["Sugestão de compra"],
            registro["Item"],
        ),
    )
