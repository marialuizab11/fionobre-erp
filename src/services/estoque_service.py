from decimal import Decimal
from sqlalchemy.orm import Session
from src.database.models.cadastros import Item
from src.database.models.core import MovimentacaoEstoque


def baixar_estoque(
    db: Session,
    id_item: int,
    quantidade: float,
    id_usuario: int = 1,
    tipo_movimento: str = "SAIDA_VENDA",
):
    """
    Deduz quantidade do saldo do item e registra movimentação de saída.
    """
    item = db.query(Item).filter(Item.id_item == id_item).first()
    if not item:
        raise ValueError(f"Item com ID {id_item} não foi encontrado.")

    qtd_decimal = Decimal(str(quantidade))

    if item.saldo_estoque < qtd_decimal:
        raise ValueError(
            f"Saldo insuficiente para o item '{item.descricao}'. "
            f"Disponível: {item.saldo_estoque}, Solicitado: {qtd_decimal}"
        )

    item.saldo_estoque -= qtd_decimal

    nova_movimentacao = MovimentacaoEstoque(
        id_item=id_item,
        id_usuario=id_usuario,
        quantidade=qtd_decimal,
        tipo_movimento=tipo_movimento,
    )

    db.add(nova_movimentacao)


def entrada_estoque(
    db: Session,
    id_item: int,
    quantidade: float,
    id_usuario: int = 1,
    tipo_movimento: str = "ENTRADA_COMPRA",
    custo_unitario: float = None,
):
    """
    Adiciona quantidade ao saldo do item, atualiza custo médio (se informado)
    e registra movimentação de entrada.
    """
    item = db.query(Item).filter(Item.id_item == id_item).first()
    if not item:
        raise ValueError(f"Item com ID {id_item} não foi encontrado.")

    qtd_decimal = Decimal(str(quantidade))
    saldo_anterior = Decimal(str(item.saldo_estoque))

    if custo_unitario is not None and qtd_decimal > 0:
        custo_decimal = Decimal(str(custo_unitario))
        if saldo_anterior + qtd_decimal > 0:
            item.custo_medio = (
                (saldo_anterior * Decimal(str(item.custo_medio)) + qtd_decimal * custo_decimal)
                / (saldo_anterior + qtd_decimal)
            )

    item.saldo_estoque = saldo_anterior + qtd_decimal

    nova_movimentacao = MovimentacaoEstoque(
        id_item=id_item,
        id_usuario=id_usuario,
        quantidade=qtd_decimal,
        tipo_movimento=tipo_movimento,
    )

    db.add(nova_movimentacao)


def estornar_estoque(
    db: Session,
    id_item: int,
    quantidade: float,
    id_usuario: int = 1,
    tipo_movimento: str = "ENTRADA_CANCELAMENTO",
):
    """
    Devolve quantidade ao estoque (ex.: cancelamento de venda ou compra).
    """
    entrada_estoque(
        db=db,
        id_item=id_item,
        quantidade=quantidade,
        id_usuario=id_usuario,
        tipo_movimento=tipo_movimento,
    )
