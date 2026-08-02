from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from src.database.models.producao import OrdemProducao, ConsumoProducao
from src.database.models.cadastros import Item
from src.database.models.log_operacao import LogOperacao
from src.services.estoque_service import baixar_estoque, entrada_estoque


def _registrar_log(db: Session, tipo_operacao: str, id_referencia: int, descricao: str, id_usuario: int):
    log = LogOperacao(
        tipo_operacao=tipo_operacao,
        origem="producao",
        id_referencia=id_referencia,
        descricao=descricao,
        id_usuario=id_usuario,
    )
    db.add(log)


def criar_ordem_producao(
    db: Session,
    id_centro_producao: int,
    id_item_produto: int,
    quantidade_planejada: float,
    id_usuario: int = 1,
):
    """
    Cria uma ordem de produção com status 'Criado'.
    """
    if quantidade_planejada <= 0:
        raise ValueError("A quantidade planejada deve ser maior que zero.")

    produto = db.query(Item).filter(Item.id_item == id_item_produto).first()
    if not produto:
        raise ValueError(f"Item produto #{id_item_produto} não encontrado.")

    nova_ordem = OrdemProducao(
        id_centro_producao=id_centro_producao,
        id_item_produto=id_item_produto,
        id_usuario=id_usuario,
        quantidade_planejada=quantidade_planejada,
        status_ordem="Criado",
    )

    db.add(nova_ordem)
    db.flush()

    _registrar_log(
        db,
        tipo_operacao="CRIAR_ORDEM_PRODUCAO",
        id_referencia=nova_ordem.id_ordem_producao,
        descricao=(
            f"Ordem de produção #{nova_ordem.id_ordem_producao} criada "
            f"para {quantidade_planejada} un. de '{produto.descricao}'."
        ),
        id_usuario=id_usuario,
    )

    try:
        db.commit()
        db.refresh(nova_ordem)
        return nova_ordem
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao criar ordem de produção: {e}")


def iniciar_producao(db: Session, id_ordem_producao: int, id_usuario: int = 1):
    """
    Inicia a produção, alterando status de 'Criado' para 'Em Producao'.
    """
    ordem = db.query(OrdemProducao).filter(
        OrdemProducao.id_ordem_producao == id_ordem_producao
    ).first()

    if not ordem:
        raise ValueError(f"Ordem de produção #{id_ordem_producao} não encontrada.")

    if ordem.status_ordem != "Criado":
        raise ValueError(
            f"Só é possível iniciar ordens com status 'Criado'. Status atual: {ordem.status_ordem}."
        )

    ordem.status_ordem = "Em Producao"
    ordem.data_inicio = datetime.utcnow()

    _registrar_log(
        db,
        tipo_operacao="INICIAR_PRODUCAO",
        id_referencia=id_ordem_producao,
        descricao=f"Produção iniciada na ordem #{id_ordem_producao}.",
        id_usuario=id_usuario,
    )

    try:
        db.commit()
        db.refresh(ordem)
        return ordem
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao iniciar produção: {e}")


def registrar_consumo(
    db: Session,
    id_ordem_producao: int,
    id_item_insumo: int,
    quantidade: float,
    id_usuario: int = 1,
):
    """
    Registra consumo de insumo durante a produção (sem baixar estoque ainda).
    """
    ordem = _obter_ordem_em_producao(db, id_ordem_producao)

    if quantidade <= 0:
        raise ValueError("A quantidade consumida deve ser maior que zero.")

    consumo = ConsumoProducao(
        id_ordem_producao=id_ordem_producao,
        id_item_insumo=id_item_insumo,
        quantidade=quantidade,
        tipo_registro="CONSUMO",
    )
    db.add(consumo)

    _registrar_log(
        db,
        tipo_operacao="REGISTRAR_CONSUMO",
        id_referencia=id_ordem_producao,
        descricao=f"Consumo de {quantidade} un. do insumo #{id_item_insumo} registrado.",
        id_usuario=id_usuario,
    )

    try:
        db.commit()
        db.refresh(consumo)
        return consumo
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao registrar consumo: {e}")


def registrar_perda(
    db: Session,
    id_ordem_producao: int,
    id_item_insumo: int,
    quantidade: float,
    id_usuario: int = 1,
):
    """
    Registra perda de insumo durante a produção (sem baixar estoque ainda).
    """
    ordem = _obter_ordem_em_producao(db, id_ordem_producao)

    if quantidade <= 0:
        raise ValueError("A quantidade de perda deve ser maior que zero.")

    perda = ConsumoProducao(
        id_ordem_producao=id_ordem_producao,
        id_item_insumo=id_item_insumo,
        quantidade=quantidade,
        tipo_registro="PERDA",
    )
    db.add(perda)

    _registrar_log(
        db,
        tipo_operacao="REGISTRAR_PERDA",
        id_referencia=id_ordem_producao,
        descricao=f"Perda de {quantidade} un. do insumo #{id_item_insumo} registrada.",
        id_usuario=id_usuario,
    )

    try:
        db.commit()
        db.refresh(perda)
        return perda
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao registrar perda: {e}")


def finalizar_producao(
    db: Session,
    id_ordem_producao: int,
    quantidade_produzida: float,
    id_usuario: int = 1,
):
    """
    Finaliza a ordem de produção em uma única transação:
    - Baixa insumos consumidos e perdas do estoque
    - Adiciona produto acabado ao estoque
    - Atualiza status para 'Finalizado'
    """
    ordem = db.query(OrdemProducao).filter(
        OrdemProducao.id_ordem_producao == id_ordem_producao
    ).first()

    if not ordem:
        raise ValueError(f"Ordem de produção #{id_ordem_producao} não encontrada.")

    if ordem.status_ordem != "Em Producao":
        raise ValueError(
            f"Só é possível finalizar ordens em produção. Status atual: {ordem.status_ordem}."
        )

    if quantidade_produzida <= 0:
        raise ValueError("A quantidade produzida deve ser maior que zero.")

    if not ordem.consumos:
        raise ValueError("Não há consumos registrados para finalizar a produção.")

    try:
        consumo_por_insumo = {}
        for registro in ordem.consumos:
            chave = registro.id_item_insumo
            qtd = Decimal(str(registro.quantidade))
            consumo_por_insumo[chave] = consumo_por_insumo.get(chave, Decimal("0")) + qtd

        for id_insumo, qtd_total in consumo_por_insumo.items():
            baixar_estoque(
                db=db,
                id_item=id_insumo,
                quantidade=float(qtd_total),
                id_usuario=id_usuario,
                tipo_movimento="SAIDA_PRODUCAO",
            )

        entrada_estoque(
            db=db,
            id_item=ordem.id_item_produto,
            quantidade=quantidade_produzida,
            id_usuario=id_usuario,
            tipo_movimento="ENTRADA_PRODUCAO",
        )

        ordem.quantidade_produzida = quantidade_produzida
        ordem.status_ordem = "Finalizado"
        ordem.data_finalizacao = datetime.utcnow()

        _registrar_log(
            db,
            tipo_operacao="FINALIZAR_PRODUCAO",
            id_referencia=id_ordem_producao,
            descricao=(
                f"Ordem #{id_ordem_producao} finalizada. "
                f"{quantidade_produzida} un. adicionadas ao estoque."
            ),
            id_usuario=id_usuario,
        )

        db.commit()
        db.refresh(ordem)
        return ordem
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao finalizar produção: {e}")


def listar_ordens_producao(db: Session, status: str = None):
    """
    Lista ordens de produção, com filtro opcional por status.
    """
    query = db.query(OrdemProducao).order_by(OrdemProducao.data_criacao.desc())

    if status:
        query = query.filter(OrdemProducao.status_ordem == status)

    return query.all()


def _obter_ordem_em_producao(db: Session, id_ordem_producao: int) -> OrdemProducao:
    ordem = db.query(OrdemProducao).filter(
        OrdemProducao.id_ordem_producao == id_ordem_producao
    ).first()

    if not ordem:
        raise ValueError(f"Ordem de produção #{id_ordem_producao} não encontrada.")

    if ordem.status_ordem != "Em Producao":
        raise ValueError(
            f"Só é possível registrar consumo/perda em ordens em produção. "
            f"Status atual: {ordem.status_ordem}."
        )

    return ordem
