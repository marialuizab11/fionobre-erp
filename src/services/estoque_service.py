from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database.models.cadastros import Item
from src.database.models.core import MovimentacaoEstoque
from src.database.models.producao import ReservaMaterial
from src.database.models.estoque import EstoqueLocalizacao, LocalizacaoEstoque

def obter_ou_criar_estoque_local(db: Session, id_item: int, id_localizacao: int) -> EstoqueLocalizacao:
    """Busca o saldo do item no local específico ou cria o registro com saldo zero."""
    estoque_local = db.query(EstoqueLocalizacao).filter(
        EstoqueLocalizacao.id_item == id_item,
        EstoqueLocalizacao.id_localizacao == id_localizacao
    ).with_for_update().first()

    if not estoque_local:
        estoque_local = EstoqueLocalizacao(
            id_item=id_item,
            id_localizacao=id_localizacao,
            quantidade=Decimal("0.00")
        )
        db.add(estoque_local)
        db.flush()
    return estoque_local


def baixar_estoque(db: Session, id_item: int, quantidade: float, id_usuario: int = 1,
                   tipo_movimento: str = "SAIDA_VENDA",
                   consumir_material_reservado: bool = False,
                   id_localizacao: int = 1):
    """Deduz o saldo global e local do item e registra a movimentacao de saida."""
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
            f"Disponível: {saldo_disponivel}, Reservado: {quantidade_reservada}, "
            f"Solicitado: {qtd_decimal}"
        )

    # Atualiza saldo global para retrocompatibilidade
    item.saldo_estoque -= qtd_decimal
    
    # Atualiza saldo na localização específica
    estoque_local = obter_ou_criar_estoque_local(db, id_item, id_localizacao)
    estoque_local.quantidade -= qtd_decimal

    db.add(MovimentacaoEstoque(
        id_item=id_item,
        id_usuario=id_usuario,
        quantidade=qtd_decimal,
        tipo_movimento=tipo_movimento,
        id_local_origem=id_localizacao
    ))
    db.commit()
    return item


def entrada_estoque(db: Session, id_item: int, quantidade: float, id_usuario: int = 1,
                    tipo_movimento: str = "ENTRADA_COMPRA", custo_unitario: float = None,
                    id_localizacao: int = 1):
    """Adiciona saldo global e local, atualiza o custo medio e registra a entrada."""
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

    # Atualiza saldo global
    item.saldo_estoque = saldo_anterior + qtd_decimal
    
    # Atualiza saldo na localização específica
    estoque_local = obter_ou_criar_estoque_local(db, id_item, id_localizacao)
    estoque_local.quantidade += qtd_decimal

    db.add(MovimentacaoEstoque(
        id_item=id_item,
        id_usuario=id_usuario,
        quantidade=qtd_decimal,
        tipo_movimento=tipo_movimento,
        id_local_destino=id_localizacao
    ))
    db.commit()
    return item


def estornar_estoque(db: Session, id_item: int, quantidade: float, id_usuario: int = 1,
                     tipo_movimento: str = "ENTRADA_CANCELAMENTO", id_localizacao: int = 1):
    """Estorna a operacao original e registra o tipo de movimento informado na localização."""
    if tipo_movimento.startswith("SAIDA_"):
        return baixar_estoque(
            db=db,
            id_item=id_item,
            quantidade=quantidade,
            id_usuario=id_usuario,
            tipo_movimento=tipo_movimento,
            id_localizacao=id_localizacao
        )
    return entrada_estoque(
        db=db,
        id_item=id_item,
        quantidade=quantidade,
        id_usuario=id_usuario,
        tipo_movimento=tipo_movimento,
        id_localizacao=id_localizacao
    )


def transferir_estoque(db: Session, id_item: int, quantidade: float, id_local_origem: int, id_local_destino: int, id_usuario: int = 1, observacao: str = None):
    """Transfere o saldo de um item de uma localização para outra."""
    qtd_decimal = Decimal(str(quantidade))
    if qtd_decimal <= 0:
        raise ValueError("A quantidade de transferência deve ser maior que zero.")
        
    origem = obter_ou_criar_estoque_local(db, id_item, id_local_origem)
    destino = obter_ou_criar_estoque_local(db, id_item, id_local_destino)
    
    if origem.quantidade < qtd_decimal:
        raise ValueError("Saldo insuficiente na localização de origem.")
        
    origem.quantidade -= qtd_decimal
    destino.quantidade += qtd_decimal
    
    db.add(MovimentacaoEstoque(
        id_item=id_item,
        id_usuario=id_usuario,
        quantidade=qtd_decimal,
        tipo_movimento="TRANSFERENCIA",
        id_local_origem=id_local_origem,
        id_local_destino=id_local_destino,
        observacao=observacao
    ))
    db.commit()


def ajustar_estoque_manual(db: Session, id_item: int, id_localizacao: int, quantidade_ajuste: float, id_usuario: int = 1, observacao: str = None):
    """Realiza um ajuste manual direto (positivo ou negativo) em uma localização."""
    if quantidade_ajuste == 0:
        raise ValueError("A quantidade de ajuste não pode ser zero.")
        
    if quantidade_ajuste > 0:
        entrada_estoque(db, id_item, quantidade_ajuste, id_usuario, "AJUSTE_ENTRADA", None, id_localizacao)
        mov = db.query(MovimentacaoEstoque).order_by(MovimentacaoEstoque.id_movimentacao.desc()).first()
        if mov: mov.observacao = observacao
    else:
        baixar_estoque(db, id_item, abs(quantidade_ajuste), id_usuario, "AJUSTE_SAIDA", False, id_localizacao)
        mov = db.query(MovimentacaoEstoque).order_by(MovimentacaoEstoque.id_movimentacao.desc()).first()
        if mov: mov.observacao = observacao
    db.commit()