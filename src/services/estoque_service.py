from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database.models.cadastros import Item
from src.database.models.core import MovimentacaoEstoque
from src.database.models.producao import ReservaMaterial


def baixar_estoque(db: Session, id_item: int, quantidade: float, id_usuario: int = 1,
                   tipo_movimento: str = "SAIDA_VENDA",
                   consumir_material_reservado: bool = False):
    """Deduz o saldo do item e registra a movimentacao de saida."""
    item = db.query(Item).filter(Item.id_item == id_item).with_for_update().first()
    if not item:
        raise ValueError(f"Item com ID {id_item} nao foi encontrado.")

    qtd_decimal = Decimal(str(quantidade))
    if qtd_decimal <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")
    quantidade_reservada = Decimal("0")
    if not consumir_material_reservado:
        quantidade_reservada = Decimal(str(
            db.query(func.coalesce(func.sum(ReservaMaterial.quantidade_reservada), 0))
            .filter(
                ReservaMaterial.id_item_insumo == id_item,
                ReservaMaterial.status_reserva == "RESERVADA",
            )
            .scalar()
        ))
    saldo_disponivel = Decimal(str(item.saldo_estoque)) - quantidade_reservada
    if saldo_disponivel < qtd_decimal:
        raise ValueError(
            f"Saldo insuficiente para o item '{item.descricao}'. "
            f"Disponivel: {saldo_disponivel}, Reservado: {quantidade_reservada}, "
            f"Solicitado: {qtd_decimal}"
        )

    item.saldo_estoque -= qtd_decimal
    db.add(MovimentacaoEstoque(
        id_item=id_item,
        id_usuario=id_usuario,
        quantidade=qtd_decimal,
        tipo_movimento=tipo_movimento,
    ))
    db.flush()
    return item


def entrada_estoque(db: Session, id_item: int, quantidade: float, id_usuario: int = 1,
                    tipo_movimento: str = "ENTRADA_COMPRA", custo_unitario: float = None):
    """Adiciona saldo, atualiza o custo medio e registra a entrada."""
    item = db.query(Item).filter(Item.id_item == id_item).with_for_update().first()
    if not item:
        raise ValueError(f"Item com ID {id_item} nao foi encontrado.")

    qtd_decimal = Decimal(str(quantidade))
    if qtd_decimal <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")

    saldo_anterior = Decimal(str(item.saldo_estoque))
    if custo_unitario is not None:
        custo_decimal = Decimal(str(custo_unitario))
        if custo_decimal < 0:
            raise ValueError("O custo unitario nao pode ser negativo.")
        item.custo_medio = (
            saldo_anterior * Decimal(str(item.custo_medio))
            + qtd_decimal * custo_decimal
        ) / (saldo_anterior + qtd_decimal)

    item.saldo_estoque = saldo_anterior + qtd_decimal
    db.add(MovimentacaoEstoque(
        id_item=id_item,
        id_usuario=id_usuario,
        quantidade=qtd_decimal,
        tipo_movimento=tipo_movimento,
    ))
    db.flush()
    return item


def estornar_estoque(db: Session, id_item: int, quantidade: float, id_usuario: int = 1,
                     tipo_movimento: str = "ENTRADA_CANCELAMENTO"):
    """Estorna a operacao original e registra o tipo de movimento informado."""
    if tipo_movimento.startswith("SAIDA_"):
        return baixar_estoque(
            db=db,
            id_item=id_item,
            quantidade=quantidade,
            id_usuario=id_usuario,
            tipo_movimento=tipo_movimento,
        )
    return entrada_estoque(
        db=db,
        id_item=id_item,
        quantidade=quantidade,
        id_usuario=id_usuario,
        tipo_movimento=tipo_movimento,
    )
