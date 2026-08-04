from datetime import date, datetime, time, timedelta
from decimal import Decimal
from sqlalchemy import func
from sqlalchemy.orm import Session
from src.database.models.producao import (
    AlocacaoCapacidadeProducao,
    CapacidadeCentroProducao,
    CentroProducao,
    ConsumoProducao,
    FichaTecnica,
    InspecaoQualidade,
    ItemFichaTecnica,
    OperacaoRoteiroProducao,
    OrdemProducao,
    OrdemOperacaoProducao,
    PlanejamentoOrdemProducao,
    ReservaMaterial,
    RoteiroProducao,
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


def configurar_capacidade_centro(
    db: Session,
    id_centro_producao: int,
    horas_disponiveis_dia,
    id_usuario: int,
    hora_inicio_expediente: str = "08:00",
    dias_uteis: str = "0,1,2,3,4",
):
    centro = db.get(CentroProducao, id_centro_producao)
    horas = Decimal(str(horas_disponiveis_dia))
    if centro is None or centro.ativo != "S":
        raise ValueError("Centro de produção inválido ou inativo.")
    if horas <= 0 or horas > 24:
        raise ValueError("A capacidade diária deve estar entre 0 e 24 horas.")
    try:
        datetime.strptime(hora_inicio_expediente, "%H:%M")
        dias = sorted({int(item) for item in dias_uteis.split(",")})
    except (ValueError, TypeError) as erro:
        raise ValueError("Horário ou dias úteis inválidos.") from erro
    if not dias or any(item < 0 or item > 6 for item in dias):
        raise ValueError("Os dias úteis devem utilizar números de 0 a 6.")

    capacidade = centro.capacidade or CapacidadeCentroProducao(
        id_centro_producao=id_centro_producao
    )
    capacidade.horas_disponiveis_dia = horas
    capacidade.hora_inicio_expediente = hora_inicio_expediente
    capacidade.dias_uteis = ",".join(str(item) for item in dias)
    db.add(capacidade)
    _registrar_log(
        db,
        "CONFIGURAR_CAPACIDADE",
        id_centro_producao,
        f"Capacidade de {centro.nome}: {horas} hora(s) por dia.",
        id_usuario,
    )
    db.commit()
    db.refresh(capacidade)
    return capacidade


def obter_roteiro_producao(db: Session, id_item_produto: int):
    return db.query(RoteiroProducao).filter(
        RoteiroProducao.id_item_produto == id_item_produto,
        RoteiroProducao.ativo == "S",
    ).first()


def salvar_roteiro_producao(
    db: Session,
    id_item_produto: int,
    operacoes: list,
    id_usuario: int,
    descricao: str = "",
):
    produto = db.get(Item, id_item_produto)
    if produto is None or produto.tipo_item != "PRODUTO_ACABADO":
        raise ValueError("O roteiro deve pertencer a um produto acabado válido.")
    if not operacoes:
        raise ValueError("O roteiro precisa ter pelo menos uma operação.")

    novas_operacoes = []
    for sequencia, item in enumerate(operacoes, start=1):
        centro = db.get(CentroProducao, int(item["id_centro_producao"]))
        if centro is None or centro.ativo != "S":
            raise ValueError("Todas as operações precisam de um centro ativo.")
        if centro.capacidade is None:
            raise ValueError(
                f"Configure a capacidade do centro '{centro.nome}' antes de usá-lo."
            )
        nome = str(item.get("nome_operacao", "")).strip()
        setup = Decimal(str(item.get("tempo_setup_horas", 0)))
        unitario = Decimal(str(item.get("tempo_unitario_horas", 0)))
        if not nome:
            raise ValueError("O nome de cada operação é obrigatório.")
        if setup < 0 or unitario < 0 or setup + unitario <= 0:
            raise ValueError("Cada operação precisa possuir tempo produtivo maior que zero.")
        novas_operacoes.append(
            OperacaoRoteiroProducao(
                sequencia=sequencia,
                id_centro_producao=centro.id_centro_producao,
                nome_operacao=nome,
                recurso=str(item.get("recurso", "")).strip() or None,
                tempo_setup_horas=setup,
                tempo_unitario_horas=unitario,
                instrucoes=str(item.get("instrucoes", "")).strip() or None,
            )
        )

    roteiro = db.query(RoteiroProducao).filter(
        RoteiroProducao.id_item_produto == id_item_produto
    ).first()
    acao = "ATUALIZAR_ROTEIRO" if roteiro else "CRIAR_ROTEIRO"
    if roteiro is None:
        roteiro = RoteiroProducao(id_item_produto=id_item_produto)
        db.add(roteiro)
    elif roteiro.planejamentos:
        raise ValueError(
            "Este roteiro já foi utilizado em ordens e tornou-se imutável para "
            "preservar a rastreabilidade do planejamento."
        )
    roteiro.descricao = descricao.strip() or None
    roteiro.ativo = "S"
    roteiro.operacoes = novas_operacoes
    db.flush()
    _registrar_log(
        db,
        acao,
        roteiro.id_roteiro,
        f"Roteiro de '{produto.descricao}' salvo com {len(operacoes)} operação(ões).",
        id_usuario,
    )
    db.commit()
    db.refresh(roteiro)
    return roteiro


def _dias_capacidade(capacidade: CapacidadeCentroProducao) -> set[int]:
    return {int(item) for item in capacidade.dias_uteis.split(",")}


def _inicio_expediente(capacidade: CapacidadeCentroProducao) -> time:
    return datetime.strptime(capacidade.hora_inicio_expediente, "%H:%M").time()


def _carga_centro_dia(db: Session, id_centro: int, dia: date) -> Decimal:
    valor = (
        db.query(func.coalesce(func.sum(AlocacaoCapacidadeProducao.horas_alocadas), 0))
        .join(AlocacaoCapacidadeProducao.ordem_operacao)
        .join(OrdemOperacaoProducao.ordem)
        .filter(
            AlocacaoCapacidadeProducao.id_centro_producao == id_centro,
            AlocacaoCapacidadeProducao.data_alocacao == dia,
            OrdemProducao.status_ordem != "Cancelado",
        )
        .scalar()
    )
    return Decimal(str(valor or 0))


def _alocar_operacao(
    db: Session,
    ordem_operacao: OrdemOperacaoProducao,
    capacidade: CapacidadeCentroProducao,
    inicio_minimo: datetime,
) -> tuple[datetime, datetime]:
    restante = Decimal(str(ordem_operacao.carga_horas))
    limite_diario = Decimal(str(capacidade.horas_disponiveis_dia))
    dias_uteis = _dias_capacidade(capacidade)
    dia = inicio_minimo.date()
    inicio_real = None
    fim_real = None

    while restante > 0:
        if dia.weekday() not in dias_uteis:
            dia += timedelta(days=1)
            continue
        base = datetime.combine(dia, _inicio_expediente(capacidade))
        usado = _carga_centro_dia(db, ordem_operacao.id_centro_producao, dia)
        deslocamento_minimo = Decimal("0")
        if dia == inicio_minimo.date() and inicio_minimo > base:
            deslocamento_minimo = Decimal(
                str((inicio_minimo - base).total_seconds() / 3600)
            )
        inicio_horas = max(usado, deslocamento_minimo)
        disponivel = limite_diario - inicio_horas
        if disponivel <= 0:
            dia += timedelta(days=1)
            continue
        alocado = min(restante, disponivel).quantize(Decimal("0.01"))
        if alocado <= 0:
            dia += timedelta(days=1)
            continue
        inicio_parcela = base + timedelta(hours=float(inicio_horas))
        fim_parcela = inicio_parcela + timedelta(hours=float(alocado))
        if inicio_real is None:
            inicio_real = inicio_parcela
        fim_real = fim_parcela
        db.add(
            AlocacaoCapacidadeProducao(
                ordem_operacao=ordem_operacao,
                id_centro_producao=ordem_operacao.id_centro_producao,
                data_alocacao=dia,
                horas_alocadas=alocado,
            )
        )
        db.flush()
        restante -= alocado
        if restante > 0:
            dia += timedelta(days=1)
    return inicio_real, fim_real


def _planejar_roteiro_ordem(
    db: Session,
    ordem: OrdemProducao,
    roteiro: RoteiroProducao,
    data_inicio_planejada: date | datetime,
) -> PlanejamentoOrdemProducao:
    if not roteiro.operacoes:
        raise ValueError("O roteiro selecionado não possui operações.")
    cursor = (
        data_inicio_planejada
        if isinstance(data_inicio_planejada, datetime)
        else datetime.combine(data_inicio_planejada, time.min)
    )
    carga_total = Decimal("0.00")
    for modelo in roteiro.operacoes:
        capacidade = (
            db.query(CapacidadeCentroProducao)
            .filter(
                CapacidadeCentroProducao.id_centro_producao
                == modelo.id_centro_producao
            )
            .with_for_update()
            .first()
        )
        if capacidade is None:
            raise ValueError(f"O centro '{modelo.centro.nome}' não possui capacidade configurada.")
        carga = (
            Decimal(str(modelo.tempo_setup_horas))
            + Decimal(str(modelo.tempo_unitario_horas))
            * Decimal(str(ordem.quantidade_planejada))
        ).quantize(Decimal("0.01"))
        operacao = OrdemOperacaoProducao(
            ordem=ordem,
            id_operacao_roteiro=modelo.id_operacao_roteiro,
            id_centro_producao=modelo.id_centro_producao,
            sequencia=modelo.sequencia,
            nome_operacao=modelo.nome_operacao,
            recurso=modelo.recurso,
            carga_horas=carga,
            inicio_planejado=cursor,
            fim_planejado=cursor,
        )
        db.add(operacao)
        db.flush()
        inicio, fim = _alocar_operacao(db, operacao, capacidade, cursor)
        operacao.inicio_planejado = inicio
        operacao.fim_planejado = fim
        cursor = fim
        carga_total += carga
    planejamento = PlanejamentoOrdemProducao(
        ordem=ordem,
        roteiro=roteiro,
        data_inicio_planejada=ordem.operacoes[0].inicio_planejado,
        data_fim_planejada=ordem.operacoes[-1].fim_planejado,
        carga_total_horas=carga_total,
        status_planejamento="PLANEJADO",
    )
    db.add(planejamento)
    return planejamento


def consultar_carga_centros(
    db: Session, data_inicio: date, data_fim: date
) -> list[dict]:
    alocacoes = db.query(AlocacaoCapacidadeProducao).filter(
        AlocacaoCapacidadeProducao.data_alocacao >= data_inicio,
        AlocacaoCapacidadeProducao.data_alocacao <= data_fim,
    ).all()
    consolidado = {}
    for item in alocacoes:
        if item.ordem_operacao.ordem.status_ordem == "Cancelado":
            continue
        chave = (item.id_centro_producao, item.data_alocacao)
        linha = consolidado.setdefault(
            chave,
            {
                "centro": item.centro.nome,
                "data": item.data_alocacao,
                "capacidade": Decimal(str(item.centro.capacidade.horas_disponiveis_dia)),
                "alocado": Decimal("0.00"),
            },
        )
        linha["alocado"] += Decimal(str(item.horas_alocadas))
    for linha in consolidado.values():
        linha["disponivel"] = linha["capacidade"] - linha["alocado"]
        linha["ocupacao_percentual"] = (
            linha["alocado"] / linha["capacidade"] * 100
            if linha["capacidade"]
            else Decimal("0")
        )
    return sorted(consolidado.values(), key=lambda item: (item["data"], item["centro"]))


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
    data_inicio_planejada: date | datetime | None = None,
    id_roteiro: int | None = None,
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

    roteiro = db.get(RoteiroProducao, id_roteiro) if id_roteiro else obter_roteiro_producao(
        db, id_item_produto
    )
    if roteiro is not None:
        if roteiro.id_item_produto != id_item_produto or roteiro.ativo != "S":
            raise ValueError("O roteiro selecionado não pertence ao produto da ordem.")
        _planejar_roteiro_ordem(
            db,
            nova_ordem,
            roteiro,
            data_inicio_planejada or date.today(),
        )

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
    if ordem.planejamento:
        ordem.planejamento.status_planejamento = "EM_EXECUCAO"
    if ordem.operacoes:
        primeira = ordem.operacoes[0]
        primeira.status_operacao = "EM_EXECUCAO"
        primeira.inicio_real = datetime.utcnow()

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


def atualizar_operacao_ordem(
    db: Session,
    id_ordem_operacao: int,
    novo_status: str,
    id_usuario: int,
) -> OrdemOperacaoProducao:
    status = novo_status.strip().upper()
    if status not in {"PENDENTE", "EM_EXECUCAO", "CONCLUIDA"}:
        raise ValueError("Status de operação inválido.")
    operacao = db.get(OrdemOperacaoProducao, id_ordem_operacao)
    if operacao is None:
        raise ValueError("Operação da ordem não encontrada.")
    if operacao.ordem.status_ordem not in {"Criado", "Em Producao"}:
        raise ValueError("A ordem não permite alterar suas operações.")
    if status == "EM_EXECUCAO":
        anteriores = [
            item
            for item in operacao.ordem.operacoes
            if item.sequencia < operacao.sequencia
            and item.status_operacao != "CONCLUIDA"
        ]
        if anteriores:
            raise ValueError("Conclua as operações anteriores antes de iniciar esta etapa.")
        operacao.inicio_real = operacao.inicio_real or datetime.utcnow()
    elif status == "CONCLUIDA":
        if operacao.status_operacao != "EM_EXECUCAO":
            raise ValueError("Somente uma operação em execução pode ser concluída.")
        operacao.fim_real = datetime.utcnow()
        proxima = next(
            (
                item
                for item in operacao.ordem.operacoes
                if item.sequencia == operacao.sequencia + 1
            ),
            None,
        )
        if proxima:
            proxima.status_operacao = "EM_EXECUCAO"
            proxima.inicio_real = datetime.utcnow()
    operacao.status_operacao = status
    _registrar_log(
        db,
        "ATUALIZAR_OPERACAO_ROTEIRO",
        operacao.ordem.id_ordem_producao,
        f"Operação '{operacao.nome_operacao}' atualizada para {status}.",
        id_usuario,
    )
    db.commit()
    db.refresh(operacao)
    return operacao


def registrar_inspecao_qualidade(
    db: Session,
    id_ordem_producao: int,
    etapa: str,
    resultado: str,
    quantidade_inspecionada,
    quantidade_aprovada,
    quantidade_reprovada,
    id_usuario: int,
    observacao: str = "",
    id_ordem_operacao: int | None = None,
) -> InspecaoQualidade:
    ordem = db.get(OrdemProducao, id_ordem_producao)
    if ordem is None:
        raise ValueError("Ordem de produção não encontrada.")
    if ordem.status_ordem != "Em Producao":
        raise ValueError("A inspeção só pode ser registrada durante a produção.")
    etapa_normalizada = etapa.strip().upper()
    resultado_normalizado = resultado.strip().upper()
    if etapa_normalizada not in {"DURANTE", "FINAL"}:
        raise ValueError("Etapa de inspeção inválida.")
    if resultado_normalizado not in {"APROVADO", "REPROVADO", "CONDICIONAL"}:
        raise ValueError("Resultado de inspeção inválido.")
    inspecionada = Decimal(str(quantidade_inspecionada))
    aprovada = Decimal(str(quantidade_aprovada))
    reprovada = Decimal(str(quantidade_reprovada))
    if inspecionada <= 0 or aprovada < 0 or reprovada < 0:
        raise ValueError("As quantidades da inspeção são inválidas.")
    if aprovada + reprovada != inspecionada:
        raise ValueError(
            "A soma aprovada e reprovada deve igualar a quantidade inspecionada."
        )
    if resultado_normalizado == "APROVADO" and reprovada > 0:
        raise ValueError("Uma inspeção aprovada não pode possuir itens reprovados.")
    if id_ordem_operacao:
        operacao = db.get(OrdemOperacaoProducao, id_ordem_operacao)
        if operacao is None or operacao.id_ordem_producao != id_ordem_producao:
            raise ValueError("A operação informada não pertence à ordem.")

    inspecao = InspecaoQualidade(
        id_ordem_producao=id_ordem_producao,
        id_ordem_operacao=id_ordem_operacao,
        etapa=etapa_normalizada,
        resultado=resultado_normalizado,
        quantidade_inspecionada=inspecionada,
        quantidade_aprovada=aprovada,
        quantidade_reprovada=reprovada,
        observacao=observacao.strip() or None,
        id_usuario=id_usuario,
    )
    db.add(inspecao)
    db.flush()
    _registrar_log(
        db,
        "REGISTRAR_INSPECAO_QUALIDADE",
        id_ordem_producao,
        f"Inspeção {etapa_normalizada}: {resultado_normalizado}.",
        id_usuario,
    )
    db.commit()
    db.refresh(inspecao)
    return inspecao


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

    if ordem.planejamento:
        aprovacao_final = next(
            (
                item
                for item in ordem.inspecoes_qualidade
                if item.etapa == "FINAL" and item.resultado == "APROVADO"
            ),
            None,
        )
        if aprovacao_final is None:
            raise ValueError(
                "A ordem possui roteiro e exige uma inspeção final aprovada antes da finalização."
            )

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
        if ordem.planejamento:
            ordem.planejamento.status_planejamento = "CONCLUIDO"
        for operacao in ordem.operacoes:
            operacao.status_operacao = "CONCLUIDA"
            operacao.inicio_real = operacao.inicio_real or ordem.data_inicio
            operacao.fim_real = operacao.fim_real or datetime.utcnow()

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
        if ordem.planejamento:
            ordem.planejamento.status_planejamento = "CANCELADO"
        for operacao in ordem.operacoes:
            if operacao.status_operacao != "CONCLUIDA":
                operacao.status_operacao = "CANCELADA"
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
