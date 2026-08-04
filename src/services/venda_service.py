from datetime import datetime, time
from decimal import Decimal

from sqlalchemy.orm import Session

from src.database.models.cadastros import Cliente
from src.database.models.financeiro import LancamentoFinanceiro
from src.database.models.logistica import Entrega
from src.database.models.usuarios import Usuario
from src.database.models.vendas import ItemVenda, PedidoVenda, PedidoVendaHistorico
from src.services.auth_service import UsuarioAutenticado, exigir_permissao, registrar_log
from src.services.estoque_service import baixar_estoque, estornar_estoque


def criar_pedido_venda(db: Session, id_cliente: int, itens_comprados: list,
                       usuario: UsuarioAutenticado):
    """Cria um pedido, baixa o estoque e registra autoria e historico."""
    exigir_permissao(usuario, "vendas.gerenciar")
    try:
        if not itens_comprados:
            raise ValueError("Um pedido precisa ter pelo menos um item.")

        cliente = db.get(Cliente, id_cliente)
        usuario_db = db.get(Usuario, usuario.id_usuario)
        if cliente is None:
            raise ValueError("Cliente nao encontrado.")
        if usuario_db is None or not usuario_db.ativo:
            raise PermissionError("Usuario responsavel invalido ou inativo.")

        ids_itens = [int(linha["id_item"]) for linha in itens_comprados]
        if len(ids_itens) != len(set(ids_itens)):
            raise ValueError("O mesmo item nao pode aparecer mais de uma vez no pedido.")

        novo_pedido = PedidoVenda(
            id_cliente=id_cliente,
            id_usuario=usuario.id_usuario,
            status_venda="Confirmado",
            valor_total_pedido=Decimal("0.00"),
        )
        db.add(novo_pedido)
        db.flush()

        valor_total = Decimal("0.00")
        for linha in itens_comprados:
            id_item = int(linha["id_item"])
            quantidade = Decimal(str(linha["quantidade"]))
            valor_unitario = Decimal(str(linha["valor_unitario"]))
            if valor_unitario < 0:
                raise ValueError("O valor unitario nao pode ser negativo.")

            item_estoque = baixar_estoque(
                db=db,
                id_item=id_item,
                quantidade=quantidade,
                id_usuario=usuario.id_usuario,
            )
            if item_estoque.tipo_item != "PRODUTO_ACABADO":
                raise ValueError(
                    f"O item '{item_estoque.descricao}' nao e um produto acabado para venda."
                )

            valor_total += quantidade * valor_unitario
            db.add(ItemVenda(
                id_pedido_venda=novo_pedido.id_pedido_venda,
                id_item=id_item,
                quantidade_vendida=quantidade,
                valor_unitario=valor_unitario,
            ))

        novo_pedido.valor_total_pedido = valor_total
        db.add(PedidoVendaHistorico(
            id_pedido_venda=novo_pedido.id_pedido_venda,
            id_usuario=usuario.id_usuario,
            nome_usuario=usuario.nome,
            status_anterior=None,
            status_novo="Confirmado",
            justificativa="Criacao do pedido",
        ))
        registrar_log(
            db,
            usuario_db,
            modulo="VENDAS",
            acao="CONFIRMAR_PEDIDO",
            entidade="PedidoVenda",
            id_registro=novo_pedido.id_pedido_venda,
            detalhes={"cliente_id": id_cliente, "itens": ids_itens, "valor_total": valor_total},
        )
        db.commit()
        db.refresh(novo_pedido)
        return novo_pedido
    except (ValueError, PermissionError):
        db.rollback()
        raise
    except Exception as erro:
        db.rollback()
        raise RuntimeError(f"Erro ao processar a venda no banco: {erro}") from erro


def cancelar_venda(db: Session, id_pedido: int, justificativa: str,
                   id_usuario: int = 1, nome_usuario: str = None):
    pedido = db.query(PedidoVenda).filter(PedidoVenda.id_pedido_venda == id_pedido).first()
    if not pedido:
        raise ValueError(f"Pedido com ID {id_pedido} nao encontrado.")
    if pedido.status_venda in ["Cancelado", "Concluido", "Concluído"]:
        raise ValueError(f"O pedido nao pode ser cancelado pois o status atual e '{pedido.status_venda}'.")
    if not justificativa or len(justificativa.strip()) < 5:
        raise ValueError("E obrigatorio fornecer uma justificativa valida para o cancelamento.")

    entrega = None
    if pedido.id_entrega:
        entrega = db.query(Entrega).filter(Entrega.id_entrega == pedido.id_entrega).first()
        if entrega and entrega.status_logistica in ["Enviado", "Entregue"]:
            raise ValueError("O pedido nao pode ser cancelado pois a mercadoria ja foi enviada.")

    status_antigo = pedido.status_venda
    pedido.status_venda = "Cancelado"
    pedido.justificativa_cancelamento = justificativa
    db.add(PedidoVendaHistorico(
        id_pedido_venda=id_pedido,
        id_usuario=id_usuario,
        nome_usuario=nome_usuario,
        status_anterior=status_antigo,
        status_novo="Cancelado",
        justificativa=justificativa,
    ))

    itens_vendidos = db.query(ItemVenda).filter(ItemVenda.id_pedido_venda == id_pedido).all()
    for item in itens_vendidos:
        estornar_estoque(db, item.id_item, item.quantidade_vendida, id_usuario)

    if entrega:
        entrega.status_logistica = "Falha"

    lancamentos = db.query(LancamentoFinanceiro).filter(
        LancamentoFinanceiro.id_pedido_venda == id_pedido
    ).all()
    for lancamento in lancamentos:
        if lancamento.status_pagamento == "Pendente":
            lancamento.status_pagamento = "Cancelado"

    try:
        db.commit()
        db.refresh(pedido)
        return pedido
    except Exception as erro:
        db.rollback()
        raise RuntimeError(f"Erro ao processar o cancelamento da venda: {erro}") from erro


def listar_pedidos(db: Session, status: str = None, data_inicio: datetime = None,
                   data_fim: datetime = None):
    query = db.query(PedidoVenda)
    if status:
        query = query.filter(PedidoVenda.status_venda == status)
    if data_inicio:
        query = query.filter(PedidoVenda.data_venda >= datetime.combine(data_inicio, time.min))
    if data_fim:
        query = query.filter(PedidoVenda.data_venda <= datetime.combine(data_fim, time.max))
    return query.order_by(PedidoVenda.data_venda.desc()).all()


def listar_historico_pedido(db: Session, id_pedido: int):
    return (
        db.query(PedidoVendaHistorico)
        .filter(PedidoVendaHistorico.id_pedido_venda == id_pedido)
        .order_by(PedidoVendaHistorico.data_hora.desc())
        .all()
    )
