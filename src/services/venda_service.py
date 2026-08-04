from datetime import datetime, time
from decimal import Decimal

from sqlalchemy.orm import Session

from src.database.models.cadastros import Cliente
from src.database.models.financeiro import LancamentoFinanceiro
from src.database.models.logistica import Entrega
from src.database.models.usuarios import Usuario
from src.database.models.vendas import ItemVenda, PedidoVenda, PedidoVendaHistorico
from src.services.auth_service import UsuarioAutenticado, exigir_permissao, registrar_log
from src.services.estoque_service import baixar_estoque, entrada_estoque, estornar_estoque


def criar_pedido_venda(
    db: Session,
    id_cliente: int,
    itens_comprados: list,
    usuario: UsuarioAutenticado
):
    """Cria um pedido, baixa o estoque e registra autoria e historico."""
    exigir_permissao(usuario, "vendas.gerenciar")
    try:
        if not itens_comprados:
            raise ValueError("Um pedido precisa ter pelo menos um item.")

        cliente = db.get(Cliente, id_cliente)
        usuario_db = db.get(Usuario, usuario.id_usuario)
        if cliente is None:
            raise ValueError("Cliente não encontrado.")
        if usuario_db is None or not usuario_db.ativo:
            raise PermissionError("Usuário responsável inválido ou inativo.")

        ids_itens = [int(linha["id_item"]) for linha in itens_comprados]
        if len(ids_itens) != len(set(ids_itens)):
            raise ValueError("O mesmo item não pode aparecer mais de uma vez no pedido.")

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
                raise ValueError("O valor unitário não pode ser negativo.")

            item_estoque = baixar_estoque(
                db=db,
                id_item=id_item,
                quantidade=quantidade,
                id_usuario=usuario.id_usuario,
            )
            if item_estoque.tipo_item != "PRODUTO_ACABADO":
                raise ValueError(
                    f"O item '{item_estoque.descricao}' não é um produto acabado para venda."
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
            justificativa="Criação do pedido",
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


def cancelar_venda(
    db: Session,
    id_pedido: int,
    justificativa: str,
    id_usuario: int = 1,
    nome_usuario: str = None
):
    pedido = db.query(PedidoVenda).filter(PedidoVenda.id_pedido_venda == id_pedido).first()
    if not pedido:
        raise ValueError(f"Pedido com ID {id_pedido} não encontrado.")
    if pedido.status_venda in ["Cancelado", "Concluido", "Concluído"]:
        raise ValueError(f"O pedido não pode ser cancelado pois o status atual é '{pedido.status_venda}'.")
    if not justificativa or len(justificativa.strip()) < 5:
        raise ValueError("É obrigatório fornecer uma justificativa válida para o cancelamento.")

    entrega = None
    if pedido.id_entrega:
        entrega = db.query(Entrega).filter(Entrega.id_entrega == pedido.id_entrega).first()
        if entrega and entrega.status_logistica in ["Enviado", "Entregue"]:
            raise ValueError("O pedido não pode ser cancelado pois a mercadoria já foi enviada.")

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


def listar_pedidos(
    db: Session,
    status: str = None,
    data_inicio: datetime = None,
    data_fim: datetime = None
):
    query = db.query(PedidoVenda)
    
    if status and str(status).strip() and str(status).strip() != "None":
        query = query.filter(PedidoVenda.status_venda == status)
        
    if data_inicio:
        query = query.filter(PedidoVenda.data_venda >= datetime.combine(data_inicio, time.min))
    if data_fim:
        query = query.filter(PedidoVenda.data_venda <= datetime.combine(data_fim, time.max))
    
    resultado = query.order_by(PedidoVenda.data_venda.desc()).all()
    return resultado if resultado is not None else []

def listar_historico_pedido(db: Session, id_pedido: int):
    return (
        db.query(PedidoVendaHistorico)
        .filter(PedidoVendaHistorico.id_pedido_venda == id_pedido)
        .order_by(PedidoVendaHistorico.data_hora.desc())
        .all()
    )


def criar_orcamento(
    db: Session,
    id_cliente: int,
    itens: list,
    usuario: UsuarioAutenticado
) -> PedidoVenda:
    """Cria um orçamento sem baixar estoque ou gerar financeiro."""
    exigir_permissao(usuario, "vendas.gerenciar")
    if not itens:
        raise ValueError("Um orçamento precisa ter pelo menos um item.")

    cliente = db.get(Cliente, id_cliente)
    if not cliente:
        raise ValueError("Cliente não encontrado.")

    novo_orcamento = PedidoVenda(
        id_cliente=id_cliente,
        id_usuario=usuario.id_usuario,
        status_venda="Orcamento",
        valor_total_pedido=Decimal("0.00"),
    )
    db.add(novo_orcamento)
    db.flush()

    valor_total = Decimal("0.00")
    for linha in itens:
        id_item = int(linha["id_item"])
        qtd = Decimal(str(linha["quantidade"]))
        vlr = Decimal(str(linha["valor_unitario"]))
        if qtd <= 0 or vlr < 0:
            raise ValueError("Quantidade e valor unitário devem ser válidos.")
        
        valor_total += qtd * vlr
        db.add(ItemVenda(
            id_pedido_venda=novo_orcamento.id_pedido_venda,
            id_item=id_item,
            quantidade_vendida=qtd,
            valor_unitario=vlr,
        ))

    novo_orcamento.valor_total_pedido = valor_total
    db.add(PedidoVendaHistorico(
        id_pedido_venda=novo_orcamento.id_pedido_venda,
        id_usuario=usuario.id_usuario,
        nome_usuario=usuario.nome,
        status_novo="Orcamento",
        justificativa="Criação do Orçamento",
    ))
    db.commit()
    db.refresh(novo_orcamento)
    return novo_orcamento


def converter_orcamento_em_venda(
    db: Session,
    id_pedido: int,
    usuario: UsuarioAutenticado
) -> PedidoVenda:
    """Converte um orçamento existente em um pedido de venda confirmado, baixando estoque."""
    exigir_permissao(usuario, "vendas.gerenciar")
    pedido = db.get(PedidoVenda, id_pedido)
    if not pedido or pedido.status_venda != "Orcamento":
        raise ValueError("Orçamento não encontrado ou já convertido.")

    for iv in pedido.itens:
        baixar_estoque(
            db=db,
            id_item=iv.id_item,
            quantidade=iv.quantidade_vendida,
            id_usuario=usuario.id_usuario,
        )

    pedido.status_venda = "Confirmado"
    db.add(PedidoVendaHistorico(
        id_pedido_venda=pedido.id_pedido_venda,
        id_usuario=usuario.id_usuario,
        nome_usuario=usuario.nome,
        status_anterior="Orcamento",
        status_novo="Confirmado",
        justificativa="Conversão de Orçamento para Pedido de Venda",
    ))
    db.commit()
    db.refresh(pedido)
    return pedido


def editar_pedido_venda(
    db: Session,
    id_pedido: int,
    novos_itens: list,
    usuario: UsuarioAutenticado
) -> PedidoVenda:
    """Edita itens de um pedido de venda antes do envio logístico, reajustando o estoque."""
    exigir_permissao(usuario, "vendas.gerenciar")
    pedido = db.get(PedidoVenda, id_pedido)
    if not pedido:
        raise ValueError(f"Pedido #{id_pedido} não encontrado.")

    if pedido.status_venda in ["Cancelado", "Concluído", "Concluido"]:
        raise ValueError("Pedidos cancelados ou concluídos não podem ser editados.")

    if pedido.entrega and pedido.entrega.status_logistica in ["Enviado", "Entregue"]:
        raise ValueError("O pedido já foi despachado e não pode mais ser editado.")

    if pedido.status_venda == "Confirmado":
        for iv in pedido.itens:
            estornar_estoque(db, iv.id_item, iv.quantidade_vendida, usuario.id_usuario)

    db.query(ItemVenda).filter(ItemVenda.id_pedido_venda == id_pedido).delete()

    valor_total = Decimal("0.00")
    for linha in novos_itens:
        id_item = int(linha["id_item"])
        qtd = Decimal(str(linha["quantidade"]))
        vlr = Decimal(str(linha["valor_unitario"]))

        if pedido.status_venda == "Confirmado":
            baixar_estoque(db=db, id_item=id_item, quantidade=qtd, id_usuario=usuario.id_usuario)

        valor_total += qtd * vlr
        db.add(ItemVenda(
            id_pedido_venda=pedido.id_pedido_venda,
            id_item=id_item,
            quantidade_vendida=qtd,
            valor_unitario=vlr,
        ))

    pedido.valor_total_pedido = valor_total
    
    for lancamento in pedido.lancamentos:
        if lancamento.status_pagamento == "Pendente":
            lancamento.valor = valor_total

    db.add(PedidoVendaHistorico(
        id_pedido_venda=pedido.id_pedido_venda,
        id_usuario=usuario.id_usuario,
        nome_usuario=usuario.nome,
        status_anterior=pedido.status_venda,
        status_novo=pedido.status_venda,
        justificativa="Alteração dos itens do pedido",
    ))

    db.commit()
    db.refresh(pedido)
    return pedido


def registrar_devolucao_venda(
    db: Session,
    id_pedido: int,
    itens_devolucao: list,
    motivo: str,
    usuario: UsuarioAutenticado,
) -> PedidoVenda:
    """Registra a devolução parcial ou total de itens, devolvendo ao estoque e ajustando o financeiro."""
    exigir_permissao(usuario, "vendas.gerenciar")
    pedido = db.get(PedidoVenda, id_pedido)
    if not pedido:
        raise ValueError("Pedido não encontrado.")

    if not motivo or len(motivo.strip()) < 5:
        raise ValueError("Informe um motivo válido para a devolução (mínimo 5 caracteres).")

    valor_estorno_total = Decimal("0.00")

    for dev in itens_devolucao:
        id_item = int(dev["id_item"])
        qtd_dev = Decimal(str(dev["quantidade_devolver"]))

        item_venda = db.query(ItemVenda).filter(
            ItemVenda.id_pedido_venda == id_pedido,
            ItemVenda.id_item == id_item
        ).first()

        if not item_venda:
            continue

        if qtd_dev <= 0 or qtd_dev > item_venda.quantidade_vendida:
            raise ValueError(f"Quantidade a devolver inválida para o item #{id_item}.")

        entrada_estoque(
            db=db,
            id_item=id_item,
            quantidade=float(qtd_dev),
            id_usuario=usuario.id_usuario,
            tipo_movimento="ENTRADA_DEVOLUCAO_VENDA",
        )

        item_venda.quantidade_vendida -= qtd_dev
        valor_estorno_total += qtd_dev * item_venda.valor_unitario

    pedido.valor_total_pedido -= valor_estorno_total

    for lancamento in pedido.lancamentos:
        if lancamento.status_pagamento == "Pendente":
            lancamento.valor -= valor_estorno_total
            if lancamento.valor <= 0:
                lancamento.status_pagamento = "Cancelado"

    db.add(PedidoVendaHistorico(
        id_pedido_venda=pedido.id_pedido_venda,
        id_usuario=usuario.id_usuario,
        nome_usuario=usuario.nome,
        status_anterior=pedido.status_venda,
        status_novo=pedido.status_venda,
        justificativa=f"Devolução registrada: {motivo}. Estorno: R$ {valor_estorno_total:.2f}",
    ))

    db.commit()
    db.refresh(pedido)
    return pedido