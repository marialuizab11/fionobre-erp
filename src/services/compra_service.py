from datetime import datetime
from sqlalchemy.orm import Session
from src.database.models.compras import PedidoCompra, ItemCompra
from src.database.models.log_operacao import LogOperacao
from src.services.estoque_service import entrada_estoque, estornar_estoque
from src.services.financeiro_service import gerar_conta_pagar, cancelar_lancamentos_pedido_compra


def _registrar_log(db: Session, tipo_operacao: str, id_referencia: int, descricao: str, id_usuario: int):
    log = LogOperacao(
        tipo_operacao=tipo_operacao,
        origem="compra",
        id_referencia=id_referencia,
        descricao=descricao,
        id_usuario=id_usuario,
    )
    db.add(log)


def criar_pedido_compra(
    db: Session,
    id_fornecedor: int,
    itens: list,
    id_usuario: int = 1,
):
    """
    Cria um pedido de compra com status 'Criado'.
    itens = [{"id_item": 1, "quantidade": 10.0, "custo_unitario": 25.00}, ...]
    """
    if not itens:
        raise ValueError("Um pedido de compra precisa ter pelo menos um item.")

    novo_pedido = PedidoCompra(
        id_fornecedor=id_fornecedor,
        id_usuario=id_usuario,
        status_compra="Criado",
        valor_total_pedido=0.00,
    )

    db.add(novo_pedido)
    db.flush()

    valor_total = 0.00

    for linha in itens:
        qtd = linha["quantidade"]
        custo = linha["custo_unitario"]
        subtotal = qtd * custo
        valor_total += subtotal

        db.add(ItemCompra(
            id_pedido_compra=novo_pedido.id_pedido_compra,
            id_item=linha["id_item"],
            quantidade_comprada=qtd,
            custo_unitario=custo,
        ))

    novo_pedido.valor_total_pedido = valor_total

    _registrar_log(
        db,
        tipo_operacao="CRIAR_PEDIDO_COMPRA",
        id_referencia=novo_pedido.id_pedido_compra,
        descricao=f"Pedido de compra #{novo_pedido.id_pedido_compra} criado.",
        id_usuario=id_usuario,
    )

    try:
        db.commit()
        db.refresh(novo_pedido)
        return novo_pedido
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao criar pedido de compra: {e}")


def confirmar_compra(db: Session, id_pedido_compra: int, id_usuario: int = 1):
    """
    Confirma um pedido de compra, alterando status de 'Criado' para 'Confirmado'.
    """
    pedido = db.query(PedidoCompra).filter(
        PedidoCompra.id_pedido_compra == id_pedido_compra
    ).first()

    if not pedido:
        raise ValueError(f"Pedido de compra #{id_pedido_compra} não encontrado.")

    if pedido.status_compra != "Criado":
        raise ValueError(
            f"Só é possível confirmar pedidos com status 'Criado'. Status atual: {pedido.status_compra}."
        )

    pedido.status_compra = "Confirmado"

    _registrar_log(
        db,
        tipo_operacao="CONFIRMAR_COMPRA",
        id_referencia=id_pedido_compra,
        descricao=f"Pedido de compra #{id_pedido_compra} confirmado.",
        id_usuario=id_usuario,
    )

    try:
        db.commit()
        db.refresh(pedido)
        return pedido
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao confirmar compra: {e}")


def receber_compra(
    db: Session,
    id_pedido_compra: int,
    data_vencimento: datetime,
    id_usuario: int = 1,
):
    """
    Recebe um pedido de compra confirmado em uma única transação:
    - Atualiza status para 'Recebido'
    - Aumenta estoque e atualiza custo médio
    - Registra MovimentacaoEstoque
    - Gera conta a pagar
    - Registra LogOperacao
    """
    pedido = db.query(PedidoCompra).filter(
        PedidoCompra.id_pedido_compra == id_pedido_compra
    ).first()

    if not pedido:
        raise ValueError(f"Pedido de compra #{id_pedido_compra} não encontrado.")

    if pedido.status_compra != "Confirmado":
        raise ValueError(
            f"Só é possível receber pedidos confirmados. Status atual: {pedido.status_compra}."
        )

    try:
        pedido.status_compra = "Recebido"

        for item_compra in pedido.itens:
            entrada_estoque(
                db=db,
                id_item=item_compra.id_item,
                quantidade=float(item_compra.quantidade_comprada),
                id_usuario=id_usuario,
                tipo_movimento="ENTRADA_COMPRA",
                custo_unitario=float(item_compra.custo_unitario),
            )

        gerar_conta_pagar(
            db=db,
            id_pedido_compra=id_pedido_compra,
            valor_total=float(pedido.valor_total_pedido),
            data_vencimento=data_vencimento,
        )

        _registrar_log(
            db,
            tipo_operacao="RECEBER_COMPRA",
            id_referencia=id_pedido_compra,
            descricao=(
                f"Pedido de compra #{id_pedido_compra} recebido. "
                f"Estoque atualizado e conta a pagar gerada."
            ),
            id_usuario=id_usuario,
        )

        db.commit()
        db.refresh(pedido)
        return pedido
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao receber compra: {e}")


def cancelar_compra(
    db: Session,
    id_pedido_compra: int,
    justificativa: str,
    id_usuario: int = 1,
):
    """
    Cancela um pedido de compra. Se já recebido, estorna o estoque.
    """
    if not justificativa or not justificativa.strip():
        raise ValueError("A justificativa de cancelamento é obrigatória.")

    pedido = db.query(PedidoCompra).filter(
        PedidoCompra.id_pedido_compra == id_pedido_compra
    ).first()

    if not pedido:
        raise ValueError(f"Pedido de compra #{id_pedido_compra} não encontrado.")

    if pedido.status_compra == "Cancelado":
        raise ValueError("Este pedido de compra já está cancelado.")

    try:
        if pedido.status_compra == "Recebido":
            for item_compra in pedido.itens:
                estornar_estoque(
                    db=db,
                    id_item=item_compra.id_item,
                    quantidade=float(item_compra.quantidade_comprada),
                    id_usuario=id_usuario,
                    tipo_movimento="SAIDA_CANCELAMENTO_COMPRA",
                )

        pedido.status_compra = "Cancelado"
        pedido.justificativa_cancelamento = justificativa.strip()
        cancelar_lancamentos_pedido_compra(db, id_pedido_compra)

        _registrar_log(
            db,
            tipo_operacao="CANCELAR_COMPRA",
            id_referencia=id_pedido_compra,
            descricao=f"Pedido de compra #{id_pedido_compra} cancelado. Motivo: {justificativa.strip()}",
            id_usuario=id_usuario,
        )

        db.commit()
        db.refresh(pedido)
        return pedido
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao cancelar compra: {e}")


def listar_pedidos_compra(db: Session, status: str = None):
    """
    Lista pedidos de compra, com filtro opcional por status.
    """
    query = db.query(PedidoCompra).order_by(PedidoCompra.data_pedido.desc())

    if status:
        query = query.filter(PedidoCompra.status_compra == status)

    return query.all()
