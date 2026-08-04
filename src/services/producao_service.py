from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from src.database.models.producao import (
    CentroProducao,
    ConsumoProducao,
    FichaTecnica,
    ItemFichaTecnica,
    OrdemProducao,
    ReservaMaterial,
)
from src.database.models.cadastros import Item
from src.database.models.usuarios import Usuario
from src.services.auth_service import registrar_log
from src.services.estoque_service import baixar_estoque, entrada_estoque


def obter_ficha_tecnica(db: Session, id_item_produto: int):
    return db.query(FichaTecnica).filter(
        FichaTecnica.id_item_produto == id_item_produto,
        FichaTecnica.ativo == "S",
    ).first()


def salvar_ficha_tecnica(
    db: Session,
    id_item_produto: int,
    componentes: list,
    id_usuario: int,
    descricao: str = "",
):
    if not componentes:
        raise ValueError("A ficha técnica precisa ter pelo menos um insumo.")

    produto = db.get(Item, id_item_produto)
    if produto is None or produto.tipo_item != "PRODUTO_ACABADO":
        raise ValueError("A ficha técnica deve pertencer a um produto acabado válido.")

    ids_insumos = [int(item["id_item_insumo"]) for item in componentes]
    if len(ids_insumos) != len(set(ids_insumos)):
        raise ValueError("O mesmo insumo não pode aparecer mais de uma vez na ficha.")

    try:
        novos_componentes = []
        for componente in componentes:
            insumo = db.get(Item, int(componente["id_item_insumo"]))
            quantidade = Decimal(str(componente["quantidade_por_unidade"]))
            if insumo is None or insumo.tipo_item == "PRODUTO_ACABADO":
                raise ValueError("Todos os componentes devem ser matérias-primas ou insumos válidos.")
            if quantidade <= 0:
                raise ValueError("A quantidade por unidade deve ser maior que zero.")
            novos_componentes.append(
                ItemFichaTecnica(
                    id_item_insumo=insumo.id_item,
                    quantidade_por_unidade=quantidade,
                )
            )

        ficha = db.query(FichaTecnica).filter(
            FichaTecnica.id_item_produto == id_item_produto
        ).first()
        acao = "ATUALIZAR_FICHA_TECNICA" if ficha else "CRIAR_FICHA_TECNICA"
        if ficha is None:
            ficha = FichaTecnica(id_item_produto=id_item_produto)
            db.add(ficha)
        ficha.descricao = descricao.strip() or None
        ficha.ativo = "S"
        ficha.componentes = novos_componentes
        db.flush()

        _registrar_log(
            db,
            acao,
            ficha.id_ficha_tecnica,
            f"Ficha técnica de '{produto.descricao}' salva com {len(componentes)} componente(s).",
            id_usuario,
        )
        db.commit()
        db.refresh(ficha)
        return ficha
    except Exception:
        db.rollback()
        raise


def calcular_necessidade_materiais(db: Session, id_item_produto: int, quantidade_planejada):
    quantidade = Decimal(str(quantidade_planejada))
    if quantidade <= 0:
        raise ValueError("A quantidade planejada deve ser maior que zero.")
    ficha = obter_ficha_tecnica(db, id_item_produto)
    if ficha is None or not ficha.componentes:
        raise ValueError("O produto não possui ficha técnica ativa com componentes.")

    necessidades = []
    for componente in ficha.componentes:
        necessario = Decimal(str(componente.quantidade_por_unidade)) * quantidade
        reservado = sum(
            Decimal(str(reserva.quantidade_reservada))
            for reserva in componente.insumo.reservas_producao
            if reserva.status_reserva == "RESERVADA"
        )
        saldo_fisico = Decimal(str(componente.insumo.saldo_estoque))
        disponivel = saldo_fisico - reservado
        necessidades.append({
            "id_item": componente.id_item_insumo,
            "descricao": componente.insumo.descricao,
            "unidade_medida": componente.insumo.unidade_medida,
            "quantidade_por_unidade": Decimal(str(componente.quantidade_por_unidade)),
            "quantidade_necessaria": necessario,
            "saldo_fisico": saldo_fisico,
            "quantidade_reservada": reservado,
            "saldo_disponivel": disponivel,
            "quantidade_faltante": max(Decimal("0"), necessario - disponivel),
        })
    return necessidades


def criar_centro_producao(db: Session, nome: str, descricao: str, id_usuario: int):
    nome = nome.strip()
    if not nome:
        raise ValueError("O nome do centro de produção é obrigatório.")
    if db.query(CentroProducao).filter(CentroProducao.nome == nome).first():
        raise ValueError("Já existe um centro de produção com este nome.")

    try:
        centro = CentroProducao(nome=nome, descricao=descricao.strip() or None, ativo="S")
        db.add(centro)
        db.flush()
        _registrar_log(
            db, "CRIAR_CENTRO_PRODUCAO", centro.id_centro_producao,
            f"Centro de produção '{centro.nome}' cadastrado.", id_usuario,
        )
        db.commit()
        db.refresh(centro)
        return centro
    except Exception:
        db.rollback()
        raise


def _registrar_log(db: Session, tipo_operacao: str, id_referencia: int, descricao: str, id_usuario: int):
    usuario = db.get(Usuario, id_usuario)
    if usuario is None or not usuario.ativo:
        raise PermissionError("Usuário responsável pela operação é inválido ou está inativo.")
    registrar_log(
        db,
        usuario,
        modulo="PRODUCAO",
        acao=tipo_operacao,
        entidade="OrdemProducao",
        id_registro=id_referencia,
        detalhes={"descricao": descricao},
    )


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
    if produto.tipo_item != "PRODUTO_ACABADO":
        raise ValueError("A ordem de produção deve gerar um produto acabado.")

    centro = db.get(CentroProducao, id_centro_producao)
    if centro is None or centro.ativo != "S":
        raise ValueError("Centro de produção inválido ou inativo.")

    ficha = obter_ficha_tecnica(db, id_item_produto)
    if ficha is None or not ficha.componentes:
        raise ValueError("O produto não possui ficha técnica ativa com componentes.")
    ids_componentes = sorted(item.id_item_insumo for item in ficha.componentes)
    (
        db.query(Item)
        .filter(Item.id_item.in_(ids_componentes))
        .order_by(Item.id_item)
        .with_for_update()
        .all()
    )

    necessidades = calcular_necessidade_materiais(
        db, id_item_produto, quantidade_planejada
    )
    faltantes = [item for item in necessidades if item["quantidade_faltante"] > 0]
    if faltantes:
        resumo = ", ".join(
            f"{item['descricao']}: faltam {item['quantidade_faltante']} {item['unidade_medida']}"
            for item in faltantes
        )
        raise ValueError(f"Estoque insuficiente para criar a ordem. {resumo}")

    nova_ordem = OrdemProducao(
        id_centro_producao=id_centro_producao,
        id_item_produto=id_item_produto,
        id_usuario=id_usuario,
        quantidade_planejada=quantidade_planejada,
        status_ordem="Criado",
    )

    db.add(nova_ordem)
    db.flush()

    for necessidade in necessidades:
        db.add(ReservaMaterial(
            id_ordem_producao=nova_ordem.id_ordem_producao,
            id_item_insumo=necessidade["id_item"],
            quantidade_reservada=necessidade["quantidade_necessaria"],
            status_reserva="RESERVADA",
        ))

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

    _validar_limite_reserva(ordem, id_item_insumo, quantidade)

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

    _validar_limite_reserva(ordem, id_item_insumo, quantidade)

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
                consumir_material_reservado=True,
            )

        for reserva in ordem.reservas:
            consumido = consumo_por_insumo.get(reserva.id_item_insumo, Decimal("0"))
            reserva.quantidade_consumida = consumido
            reserva.status_reserva = "CONSUMIDA" if consumido > 0 else "LIBERADA"

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


def cancelar_ordem_producao(
    db: Session,
    id_ordem_producao: int,
    justificativa: str,
    id_usuario: int = 1,
):
    if not justificativa or len(justificativa.strip()) < 5:
        raise ValueError("Informe uma justificativa com pelo menos 5 caracteres.")
    ordem = db.get(OrdemProducao, id_ordem_producao)
    if ordem is None:
        raise ValueError(f"Ordem de produção #{id_ordem_producao} não encontrada.")
    if ordem.status_ordem in ["Finalizado", "Cancelado"]:
        raise ValueError(f"Não é possível cancelar uma ordem com status '{ordem.status_ordem}'.")

    try:
        ordem.status_ordem = "Cancelado"
        for reserva in ordem.reservas:
            if reserva.status_reserva == "RESERVADA":
                reserva.status_reserva = "LIBERADA"
        _registrar_log(
            db,
            "CANCELAR_ORDEM_PRODUCAO",
            id_ordem_producao,
            f"Ordem cancelada. Motivo: {justificativa.strip()}",
            id_usuario,
        )
        db.commit()
        db.refresh(ordem)
        return ordem
    except Exception as erro:
        db.rollback()
        raise RuntimeError(f"Erro ao cancelar ordem de produção: {erro}") from erro


def listar_ordens_producao(db: Session, status: str = None):
    """
    Lista ordens de produção, com filtro opcional por status.
    """
    query = db.query(OrdemProducao).order_by(OrdemProducao.data_criacao.desc())

    if status:
        query = query.filter(OrdemProducao.status_ordem == status)

    return query.all()


def _validar_limite_reserva(ordem: OrdemProducao, id_item_insumo: int, quantidade) -> None:
    reserva = next(
        (
            item for item in ordem.reservas
            if item.id_item_insumo == id_item_insumo and item.status_reserva == "RESERVADA"
        ),
        None,
    )
    if reserva is None:
        raise ValueError("O insumo não está reservado na ficha técnica desta ordem.")
    ja_apontado = sum(
        Decimal(str(item.quantidade))
        for item in ordem.consumos
        if item.id_item_insumo == id_item_insumo
    )
    total = ja_apontado + Decimal(str(quantidade))
    reservado = Decimal(str(reserva.quantidade_reservada))
    if total > reservado:
        raise ValueError(
            f"O total apontado ({total}) supera a quantidade reservada ({reservado})."
        )


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
