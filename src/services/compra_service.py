from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from src.database.models.compras import ItemCompra, NecessidadeCompra, PedidoCompra
from src.database.models.usuarios import Usuario
from src.services.auth_service import registrar_log
from src.services.estoque_service import entrada_estoque, estornar_estoque
from src.services.financeiro_service import gerar_conta_pagar, cancelar_lancamentos_pedido_compra


def _registrar_log(db: Session, tipo_operacao: str, id_referencia: int, descricao: str, id_usuario: int):
    usuario = db.get(Usuario, id_usuario)
    if usuario is None or not usuario.ativo:
        raise PermissionError("Usuário responsável pela operação é inválido ou está inativo.")
    registrar_log(
        db,
        usuario,
        modulo="COMPRAS",
        acao=tipo_operacao,
        entidade="PedidoCompra",
        id_registro=id_referencia,
        detalhes={"descricao": descricao},
    )


def criar_pedido_compra(
    db: Session,
    id_fornecedor: int,
    itens: list,
    id_usuario: int = 1,
    confirmar_transacao: bool = True,
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
        valor_total_pedido=Decimal("0.00"),
    )

    db.add(novo_pedido)
    db.flush()

    valor_total = Decimal("0.00")

    for linha in itens:
        qtd = Decimal(str(linha["quantidade"]))
        custo = Decimal(str(linha["custo_unitario"]))
        if qtd <= 0:
            raise ValueError("A quantidade comprada deve ser maior que zero.")
        if custo < 0:
            raise ValueError("O custo unitário não pode ser negativo.")
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
        if not confirmar_transacao:
            db.flush()
            return novo_pedido
        db.commit()
        db.refresh(novo_pedido)
        return novo_pedido
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao criar pedido de compra: {e}")


def gerar_necessidades_compra(
    db: Session,
    id_item_produto: int,
    necessidades: list,
    id_usuario: int,
):
    faltantes = [
        item for item in necessidades
        if Decimal(str(item["quantidade_faltante"])) > 0
    ]
    if not faltantes:
        raise ValueError("Não existem materiais faltantes para gerar necessidades de compra.")

    try:
        registros = []
        for item in faltantes:
            id_item = int(item["id_item"])
            registro = db.query(NecessidadeCompra).filter(
                NecessidadeCompra.id_item == id_item,
                NecessidadeCompra.id_item_produto == id_item_produto,
                NecessidadeCompra.status_necessidade.in_(["PENDENTE", "EM_COMPRA"]),
            ).first()
            if registro is None:
                registro = NecessidadeCompra(
                    id_item=id_item,
                    id_item_produto=id_item_produto,
                    id_usuario=id_usuario,
                    origem="PCP",
                    status_necessidade="PENDENTE",
                )
                db.add(registro)
            elif registro.status_necessidade == "EM_COMPRA":
                registros.append(registro)
                continue

            registro.quantidade_necessaria = Decimal(str(item["quantidade_necessaria"]))
            registro.saldo_disponivel = Decimal(str(item["saldo_disponivel"]))
            registro.quantidade_faltante = Decimal(str(item["quantidade_faltante"]))
            registro.id_usuario = id_usuario
            registros.append(registro)

        db.flush()
        _registrar_log(
            db,
            "GERAR_NECESSIDADE_COMPRA",
            registros[0].id_necessidade,
            f"{len(registros)} necessidade(s) de compra gerada(s) pelo PCP.",
            id_usuario,
        )
        db.commit()
        return registros
    except Exception:
        db.rollback()
        raise


def criar_pedido_por_necessidades(
    db: Session,
    id_fornecedor: int,
    ids_necessidades: list,
    custos_unitarios: dict,
    id_usuario: int,
):
    if not ids_necessidades:
        raise ValueError("Selecione pelo menos uma necessidade de compra.")
    necessidades = db.query(NecessidadeCompra).filter(
        NecessidadeCompra.id_necessidade.in_(ids_necessidades)
    ).all()
    if len(necessidades) != len(set(ids_necessidades)):
        raise ValueError("Uma ou mais necessidades não foram encontradas.")
    if any(item.status_necessidade != "PENDENTE" for item in necessidades):
        raise ValueError("Somente necessidades pendentes podem virar pedido de compra.")

    try:
        itens_por_id = {}
        for necessidade in necessidades:
            custo = Decimal(str(custos_unitarios.get(necessidade.id_item, 0)))
            if custo < 0:
                raise ValueError("O custo unitário não pode ser negativo.")
            linha = itens_por_id.setdefault(
                necessidade.id_item,
                {"id_item": necessidade.id_item, "quantidade": Decimal("0"), "custo_unitario": custo},
            )
            linha["quantidade"] += Decimal(str(necessidade.quantidade_faltante))

        pedido = criar_pedido_compra(
            db,
            id_fornecedor,
            list(itens_por_id.values()),
            id_usuario,
            confirmar_transacao=False,
        )
        for necessidade in necessidades:
            necessidade.id_pedido_compra = pedido.id_pedido_compra
            necessidade.status_necessidade = "EM_COMPRA"
        db.commit()
        db.refresh(pedido)
        return pedido
    except Exception:
        db.rollback()
        raise


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
            id_usuario=id_usuario,
        )

        for necessidade in pedido.necessidades:
            necessidade.status_necessidade = "ATENDIDA"

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
        for necessidade in pedido.necessidades:
            necessidade.status_necessidade = "PENDENTE"
            necessidade.id_pedido_compra = None

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

def editar_pedido_compra(
    db: Session,
    id_pedido_compra: int,
    id_fornecedor: int,
    itens: list,
    id_usuario: int = 1,
):
    """
    Edita um pedido de compra que ainda esteja no status 'Criado'.
    """
    pedido = db.query(PedidoCompra).filter(
        PedidoCompra.id_pedido_compra == id_pedido_compra
    ).first()

    if not pedido:
        raise ValueError(f"Pedido de compra #{id_pedido_compra} não encontrado.")

    if pedido.status_compra != "Criado":
        raise ValueError(f"Apenas pedidos com status 'Criado' podem ser editados. Status atual: {pedido.status_compra}.")

    if not itens:
        raise ValueError("O pedido de compra precisa ter pelo menos um item.")

    try:
        pedido.id_fornecedor = id_fornecedor

        # Remove os itens antigos
        db.query(ItemCompra).filter(ItemCompra.id_pedido_compra == id_pedido_compra).delete()

        # Adiciona a nova lista de itens e recalcula o total
        valor_total = Decimal("0.00")
        for linha in itens:
            qtd = Decimal(str(linha["quantidade"]))
            custo = Decimal(str(linha["custo_unitario"]))
            if qtd <= 0:
                raise ValueError("A quantidade comprada deve ser maior que zero.")
            if custo < 0:
                raise ValueError("O custo unitário não pode ser negativo.")
            
            subtotal = qtd * custo
            valor_total += subtotal

            db.add(ItemCompra(
                id_pedido_compra=pedido.id_pedido_compra,
                id_item=linha["id_item"],
                quantidade_comprada=qtd,
                custo_unitario=custo,
            ))

        pedido.valor_total_pedido = valor_total

        _registrar_log(
            db,
            tipo_operacao="EDITAR_PEDIDO_COMPRA",
            id_referencia=pedido.id_pedido_compra,
            descricao=f"Pedido de compra #{pedido.id_pedido_compra} editado.",
            id_usuario=id_usuario,
        )

        db.commit()
        db.refresh(pedido)
        return pedido
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao editar pedido de compra: {e}")


def remover_pedido_compra(db: Session, id_pedido_compra: int, id_usuario: int = 1):
    """
    Remove fisicamente um pedido de compra que esteja com status 'Criado'.
    Libera eventuais necessidades de compra do PCP associadas.
    """
    pedido = db.query(PedidoCompra).filter(
        PedidoCompra.id_pedido_compra == id_pedido_compra
    ).first()

    if not pedido:
        raise ValueError(f"Pedido de compra #{id_pedido_compra} não encontrado.")

    if pedido.status_compra != "Criado":
        raise ValueError(f"Apenas pedidos com status 'Criado' podem ser removidos. Para outros status, utilize o cancelamento.")

    try:
        # Libera necessidades do PCP se existirem
        for necessidade in pedido.necessidades:
            necessidade.status_necessidade = "PENDENTE"
            necessidade.id_pedido_compra = None

        db.query(ItemCompra).filter(ItemCompra.id_pedido_compra == id_pedido_compra).delete()
        
        _registrar_log(
            db,
            tipo_operacao="REMOVER_PEDIDO_COMPRA",
            id_referencia=pedido.id_pedido_compra,
            descricao=f"Pedido de compra #{pedido.id_pedido_compra} removido do sistema.",
            id_usuario=id_usuario,
        )

        db.delete(pedido)
        db.commit()
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao remover pedido de compra: {e}")