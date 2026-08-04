import hashlib
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy.orm import Session

from src.database.models.logistica import (
    ComprovanteEntrega,
    DevolucaoLogistica,
    Entrega,
    EntregaStatusHistorico,
    EventoRastreamentoEntrega,
    ItemDevolucaoLogistica,
    ParadaRotaEntrega,
    ReferenciaRastreamentoEntrega,
    RotaEntrega,
    Veiculo,
)
from src.database.models.usuarios import Usuario
from src.database.models.vendas import PedidoVenda, PedidoVendaHistorico
from src.services.auth_service import registrar_log
from src.services.estoque_service import entrada_estoque


STATUS_ENTREGA_VALIDOS = (
    "Pendente",
    "Em separação",
    "Pronto para expedição",
    "Enviado",
    "Em rota",
    "Tentativa de entrega",
    "Entregue",
    "Falha",
    "Devolução solicitada",
    "Devolvido",
)


def _como_datetime(valor: date | datetime) -> datetime:
    return valor if isinstance(valor, datetime) else datetime.combine(valor, time.min)


def _obter_usuario(db: Session, id_usuario: int) -> Usuario:
    usuario = db.get(Usuario, id_usuario)
    if usuario is None or not usuario.ativo:
        raise PermissionError("Usuário responsável inválido ou inativo.")
    return usuario


def _auditar(
    db: Session,
    usuario: Usuario,
    acao: str,
    entidade: str,
    id_registro: int,
    detalhes: dict | None = None,
) -> None:
    registrar_log(
        db,
        usuario,
        modulo="LOGISTICA",
        acao=acao,
        entidade=entidade,
        id_registro=id_registro,
        detalhes=detalhes,
    )


def criar_entrega_para_pedido(
    db: Session,
    id_pedido: int,
    data_previsao: date | datetime,
    valor_frete: float = 0.00,
):
    pedido = db.get(PedidoVenda, id_pedido)
    if not pedido:
        raise ValueError(f"Pedido com ID {id_pedido} não encontrado.")
    if pedido.id_entrega:
        raise ValueError("O pedido já possui uma entrega vinculada.")
    nova_entrega = Entrega(
        data_previsao=_como_datetime(data_previsao),
        status_logistica="Pendente",
        valor_frete=valor_frete,
    )
    db.add(nova_entrega)
    db.flush()
    pedido.id_entrega = nova_entrega.id_entrega
    db.commit()
    db.refresh(nova_entrega)
    return nova_entrega

def atualizar_status_logistica(db: Session, id_entrega: int, novo_status: str, id_usuario: int, nome_usuario: str):
    if not id_usuario or not nome_usuario:
        raise ValueError("A identificação do usuário é obrigatória para registrar alterações de logística.")

    entrega = db.query(Entrega).filter(Entrega.id_entrega == id_entrega).first()
    if not entrega:
        raise ValueError(f"Entrega com ID {id_entrega} não encontrada.")
        
    status_validos = ["Pendente", "Em separação", "Enviado", "Entregue", "Falha"]
    if novo_status not in status_validos:
        raise ValueError(f"Status inválido. Escolha entre: {status_validos}")

def _aplicar_status(
    db: Session,
    entrega: Entrega,
    novo_status: str,
    id_usuario: int | None,
    nome_usuario: str | None,
    descricao: str | None = None,
    localizacao: str | None = None,
) -> EventoRastreamentoEntrega:
    if novo_status == "Expedido":
        novo_status = "Enviado"
    if novo_status not in STATUS_ENTREGA_VALIDOS:
        raise ValueError(
            "Status inválido. Escolha entre: " + ", ".join(STATUS_ENTREGA_VALIDOS)
        )
    status_anterior = entrega.status_logistica
    entrega.status_logistica = novo_status
    agora = datetime.now()
    if novo_status in {"Enviado", "Em rota"}:
        entrega.data_expedicao = entrega.data_expedicao or agora
    if novo_status == "Entregue":
        entrega.data_entrega_realizada = agora
        for pedido in entrega.pedidos:
            status_pedido = pedido.status_venda
            pedido.status_venda = "Concluído"
            if status_pedido != "Concluído":
                db.add(
                    PedidoVendaHistorico(
                        id_pedido_venda=pedido.id_pedido_venda,
                        id_usuario=id_usuario,
                        nome_usuario=nome_usuario,
                        status_anterior=status_pedido,
                        status_novo="Concluído",
                        justificativa="Entrega finalizada com sucesso.",
                    )
                )
    elif novo_status == "Devolvido":
        for pedido in entrega.pedidos:
            status_pedido = pedido.status_venda
            pedido.status_venda = "Devolvido"
            if status_pedido != "Devolvido":
                db.add(
                    PedidoVendaHistorico(
                        id_pedido_venda=pedido.id_pedido_venda,
                        id_usuario=id_usuario,
                        nome_usuario=nome_usuario,
                        status_anterior=status_pedido,
                        status_novo="Devolvido",
                        justificativa="Devolução recebida pela logística.",
                    )
                )

    if status_anterior != novo_status:
        db.add(
            EntregaStatusHistorico(
                id_entrega=entrega.id_entrega,
                id_usuario=id_usuario,
                nome_usuario=nome_usuario,
                status_anterior=status_anterior,
                status_novo=novo_status,
            )
        )
    evento = EventoRastreamentoEntrega(
        id_entrega=entrega.id_entrega,
        status=novo_status,
        descricao=descricao.strip() if descricao else None,
        localizacao=localizacao.strip() if localizacao else None,
        id_usuario=id_usuario,
    )
    db.add(evento)
    for parada in entrega.paradas_rota:
        if parada.rota.status_rota in {"PLANEJADA", "EM_ROTA"}:
            parada.status_parada = {
                "Entregue": "ENTREGUE",
                "Falha": "FALHA",
                "Devolvido": "DEVOLVIDO",
                "Tentativa de entrega": "TENTATIVA",
                "Em rota": "EM_ROTA",
            }.get(novo_status, parada.status_parada)
    return evento


def atualizar_status_logistica(
    db: Session,
    id_entrega: int,
    novo_status: str,
    id_usuario: int | None = None,
    nome_usuario: str | None = None,
    descricao: str | None = None,
    localizacao: str | None = None,
):
    entrega = db.get(Entrega, id_entrega)
    if not entrega:
        raise ValueError(f"Entrega com ID {id_entrega} não encontrada.")
    usuario = _obter_usuario(db, id_usuario) if id_usuario else None
    _aplicar_status(
        db,
        entrega,
        novo_status,
        id_usuario,
        nome_usuario or (usuario.nome if usuario else None),
        descricao,
        localizacao,
    )
    if usuario:
        _auditar(
            db,
            usuario,
            "ATUALIZAR_STATUS_ENTREGA",
            "Entrega",
            id_entrega,
            {"status": novo_status, "localizacao": localizacao},
        )
    db.commit()
    db.refresh(entrega)
    return entrega


def configurar_rastreamento_externo(
    db: Session,
    id_entrega: int,
    codigo_rastreio: str,
    id_usuario: int,
    transportadora: str = "",
    url_rastreamento: str = "",
) -> ReferenciaRastreamentoEntrega:
    entrega = db.get(Entrega, id_entrega)
    usuario = _obter_usuario(db, id_usuario)
    if entrega is None:
        raise ValueError("Entrega não encontrada.")
    if not codigo_rastreio.strip():
        raise ValueError("O código de rastreamento é obrigatório.")
    referencia = entrega.rastreamento or ReferenciaRastreamentoEntrega(
        id_entrega=id_entrega
    )
    referencia.codigo_rastreio = codigo_rastreio.strip()
    referencia.transportadora = transportadora.strip() or None
    referencia.url_rastreamento = url_rastreamento.strip() or None
    referencia.data_atualizacao = datetime.utcnow()
    db.add(referencia)
    _auditar(
        db,
        usuario,
        "CONFIGURAR_RASTREAMENTO",
        "Entrega",
        id_entrega,
        {"codigo": codigo_rastreio, "transportadora": transportadora},
    )
    db.commit()
    db.refresh(referencia)
    return referencia


def registrar_evento_rastreamento(
    db: Session,
    id_entrega: int,
    status: str,
    id_usuario: int,
    descricao: str = "",
    localizacao: str = "",
) -> EventoRastreamentoEntrega:
    entrega = db.get(Entrega, id_entrega)
    usuario = _obter_usuario(db, id_usuario)
    if entrega is None:
        raise ValueError("Entrega não encontrada.")
    evento = _aplicar_status(
        db,
        entrega,
        status,
        id_usuario,
        usuario.nome,
        descricao,
        localizacao,
    )
    _auditar(
        db,
        usuario,
        "REGISTRAR_EVENTO_RASTREAMENTO",
        "Entrega",
        id_entrega,
        {"status": status, "localizacao": localizacao},
    )
    db.commit()
    db.refresh(evento)
    return evento


def criar_veiculo(
    db: Session,
    placa: str,
    descricao: str,
    capacidade_kg,
    id_usuario: int,
    motorista: str = "",
) -> Veiculo:
    usuario = _obter_usuario(db, id_usuario)
    placa_normalizada = placa.strip().upper().replace("-", "")
    capacidade = Decimal(str(capacidade_kg))
    if len(placa_normalizada) != 7:
        raise ValueError("Informe uma placa válida com sete caracteres.")
    if not descricao.strip() or capacidade <= 0:
        raise ValueError("Descrição e capacidade positiva são obrigatórias.")
    if db.query(Veiculo).filter(Veiculo.placa == placa_normalizada).first():
        raise ValueError("Já existe um veículo com esta placa.")
    veiculo = Veiculo(
        placa=placa_normalizada,
        descricao=descricao.strip(),
        motorista=motorista.strip() or None,
        capacidade_kg=capacidade,
    )
    db.add(veiculo)
    db.flush()
    _auditar(db, usuario, "CRIAR_VEICULO", "Veiculo", veiculo.id_veiculo)
    db.commit()
    db.refresh(veiculo)
    return veiculo


def criar_rota_entrega(
    db: Session,
    descricao: str,
    data_planejada: date | datetime,
    id_veiculo: int,
    entregas: list,
    id_usuario: int,
) -> RotaEntrega:
    usuario = _obter_usuario(db, id_usuario)
    veiculo = db.get(Veiculo, id_veiculo)
    if veiculo is None or veiculo.ativo != "S":
        raise ValueError("Veículo inválido ou inativo.")
    if not descricao.strip() or not entregas:
        raise ValueError("Informe a descrição e pelo menos uma entrega para a rota.")
    paradas = []
    peso_total = Decimal("0.00")
    ids = set()
    for sequencia, item in enumerate(entregas, start=1):
        id_entrega = int(item["id_entrega"])
        if id_entrega in ids:
            raise ValueError("A mesma entrega não pode aparecer duas vezes na rota.")
        ids.add(id_entrega)
        entrega = db.get(Entrega, id_entrega)
        if entrega is None or entrega.status_logistica in {"Entregue", "Devolvido"}:
            raise ValueError("Uma das entregas é inválida ou já foi encerrada.")
        rota_ativa = (
            db.query(ParadaRotaEntrega)
            .join(ParadaRotaEntrega.rota)
            .filter(
                ParadaRotaEntrega.id_entrega == id_entrega,
                RotaEntrega.status_rota.in_(["PLANEJADA", "EM_ROTA"]),
            )
            .first()
        )
        if rota_ativa:
            raise ValueError(f"A entrega #{id_entrega} já pertence a uma rota ativa.")
        peso = Decimal(str(item.get("peso_estimado_kg", 0)))
        if peso < 0:
            raise ValueError("O peso estimado não pode ser negativo.")
        peso_total += peso
        paradas.append(
            ParadaRotaEntrega(
                id_entrega=id_entrega,
                sequencia=sequencia,
                peso_estimado_kg=peso,
                observacao=str(item.get("observacao", "")).strip() or None,
            )
        )
    if peso_total > Decimal(str(veiculo.capacidade_kg)):
        raise ValueError(
            f"A carga de {peso_total} kg excede a capacidade de {veiculo.capacidade_kg} kg."
        )
    rota = RotaEntrega(
        descricao=descricao.strip(),
        data_planejada=_como_datetime(data_planejada),
        id_veiculo=id_veiculo,
        id_usuario=id_usuario,
        paradas=paradas,
    )
    db.add(rota)
    db.flush()
    _auditar(
        db,
        usuario,
        "CRIAR_ROTA",
        "RotaEntrega",
        rota.id_rota,
        {"entregas": sorted(ids), "peso_total_kg": str(peso_total)},
    )
    db.commit()
    db.refresh(rota)
    return rota


def iniciar_rota(db: Session, id_rota: int, id_usuario: int) -> RotaEntrega:
    rota = db.get(RotaEntrega, id_rota)
    usuario = _obter_usuario(db, id_usuario)
    if rota is None or rota.status_rota != "PLANEJADA":
        raise ValueError("Somente uma rota planejada pode ser iniciada.")
    rota.status_rota = "EM_ROTA"
    rota.data_inicio = datetime.now()
    for parada in rota.paradas:
        parada.status_parada = "EM_ROTA"
        _aplicar_status(
            db,
            parada.entrega,
            "Em rota",
            id_usuario,
            usuario.nome,
            f"Saiu para entrega na rota #{rota.id_rota}.",
        )
    _auditar(db, usuario, "INICIAR_ROTA", "RotaEntrega", id_rota)
    db.commit()
    db.refresh(rota)
    return rota


def finalizar_rota(db: Session, id_rota: int, id_usuario: int) -> RotaEntrega:
    rota = db.get(RotaEntrega, id_rota)
    usuario = _obter_usuario(db, id_usuario)
    if rota is None or rota.status_rota != "EM_ROTA":
        raise ValueError("Somente uma rota em andamento pode ser finalizada.")
    pendentes = [
        item
        for item in rota.paradas
        if item.status_parada not in {"ENTREGUE", "FALHA", "DEVOLVIDO"}
    ]
    if pendentes:
        raise ValueError("Finalize todas as paradas antes de concluir a rota.")
    rota.status_rota = "CONCLUIDA"
    rota.data_finalizacao = datetime.now()
    _auditar(db, usuario, "FINALIZAR_ROTA", "RotaEntrega", id_rota)
    db.commit()
    db.refresh(rota)
    return rota


def registrar_comprovante_entrega(
    db: Session,
    id_entrega: int,
    nome_recebedor: str,
    assinatura_recebedor: str,
    id_usuario: int,
    documento_recebedor: str = "",
    nome_arquivo: str | None = None,
    tipo_arquivo: str | None = None,
    conteudo_arquivo: bytes | None = None,
    observacao: str = "",
) -> ComprovanteEntrega:
    entrega = db.get(Entrega, id_entrega)
    usuario = _obter_usuario(db, id_usuario)
    if entrega is None:
        raise ValueError("Entrega não encontrada.")
    if not nome_recebedor.strip() or not assinatura_recebedor.strip():
        raise ValueError("Nome e assinatura do recebedor são obrigatórios.")
    if conteudo_arquivo and len(conteudo_arquivo) > 10 * 1024 * 1024:
        raise ValueError("O comprovante deve possuir no máximo 10 MB.")
    comprovante = entrega.comprovante or ComprovanteEntrega(id_entrega=id_entrega)
    comprovante.nome_recebedor = nome_recebedor.strip()
    comprovante.documento_recebedor = documento_recebedor.strip() or None
    comprovante.assinatura_recebedor = assinatura_recebedor.strip()
    comprovante.nome_arquivo = nome_arquivo
    comprovante.tipo_arquivo = tipo_arquivo
    comprovante.conteudo_arquivo = conteudo_arquivo
    comprovante.hash_arquivo = (
        hashlib.sha256(conteudo_arquivo).hexdigest() if conteudo_arquivo else None
    )
    comprovante.observacao = observacao.strip() or None
    comprovante.id_usuario = id_usuario
    comprovante.data_recebimento = datetime.now()
    db.add(comprovante)
    _aplicar_status(
        db,
        entrega,
        "Entregue",
        id_usuario,
        usuario.nome,
        f"Recebido por {nome_recebedor.strip()}.",
    )
    db.flush()
    _auditar(
        db,
        usuario,
        "REGISTRAR_COMPROVANTE",
        "Entrega",
        id_entrega,
        {"recebedor": nome_recebedor, "hash": comprovante.hash_arquivo},
    )
    db.commit()
    db.refresh(comprovante)
    return comprovante


def solicitar_devolucao(
    db: Session,
    id_entrega: int,
    motivo: str,
    itens: list,
    id_usuario: int,
    observacao: str = "",
) -> DevolucaoLogistica:
    entrega = db.get(Entrega, id_entrega)
    usuario = _obter_usuario(db, id_usuario)
    if entrega is None or not entrega.pedidos:
        raise ValueError("Entrega não encontrada ou sem pedido vinculado.")
    if len(motivo.strip()) < 5 or not itens:
        raise ValueError("Informe o motivo e pelo menos um item para devolução.")
    if any(
        item.status_devolucao in {"SOLICITADA", "EM_TRANSITO"}
        for item in entrega.devolucoes
    ):
        raise ValueError("A entrega já possui uma devolução em andamento.")
    vendido = {}
    for pedido in entrega.pedidos:
        for item in pedido.itens:
            vendido[item.id_item] = vendido.get(item.id_item, Decimal("0")) + Decimal(
                str(item.quantidade_vendida)
            )
    for devolucao_anterior in entrega.devolucoes:
        if devolucao_anterior.status_devolucao == "CANCELADA":
            continue
        for item in devolucao_anterior.itens:
            vendido[item.id_item] = vendido.get(item.id_item, Decimal("0")) - Decimal(
                str(item.quantidade)
            )
    linhas = []
    ids = set()
    for item in itens:
        id_item = int(item["id_item"])
        quantidade = Decimal(str(item["quantidade"]))
        if id_item in ids or quantidade <= 0 or quantidade > vendido.get(id_item, 0):
            raise ValueError("Item ou quantidade inválida para a devolução.")
        ids.add(id_item)
        condicao = str(item.get("condicao_item", "INTEGRO")).strip().upper()
        if condicao not in {"INTEGRO", "AVARIADO", "INUTILIZADO"}:
            raise ValueError("Condição do item inválida.")
        reintegrar = bool(item.get("reintegrar_estoque", condicao == "INTEGRO"))
        if condicao != "INTEGRO" and reintegrar:
            raise ValueError("Somente itens íntegros podem voltar ao estoque disponível.")
        linhas.append(
            ItemDevolucaoLogistica(
                id_item=id_item,
                quantidade=quantidade,
                condicao_item=condicao,
                reintegrar_estoque=reintegrar,
            )
        )
    devolucao = DevolucaoLogistica(
        id_entrega=id_entrega,
        motivo=motivo.strip(),
        observacao=observacao.strip() or None,
        id_usuario_solicitacao=id_usuario,
        itens=linhas,
    )
    db.add(devolucao)
    _aplicar_status(
        db,
        entrega,
        "Devolução solicitada",
        id_usuario,
        usuario.nome,
        motivo.strip(),
    )
    db.flush()
    _auditar(
        db,
        usuario,
        "SOLICITAR_DEVOLUCAO",
        "DevolucaoLogistica",
        devolucao.id_devolucao,
    )
    db.commit()
    db.refresh(devolucao)
    return devolucao


def receber_devolucao(
    db: Session, id_devolucao: int, id_usuario: int
) -> DevolucaoLogistica:
    devolucao = db.get(DevolucaoLogistica, id_devolucao)
    usuario = _obter_usuario(db, id_usuario)
    if devolucao is None or devolucao.status_devolucao not in {
        "SOLICITADA",
        "EM_TRANSITO",
    }:
        raise ValueError("A devolução não está disponível para recebimento.")
    try:
        for item in devolucao.itens:
            if item.reintegrar_estoque:
                entrada_estoque(
                    db,
                    item.id_item,
                    item.quantidade,
                    id_usuario,
                    tipo_movimento="ENTRADA_DEVOLUCAO",
                )
        devolucao.status_devolucao = "RECEBIDA"
        devolucao.id_usuario_recebimento = id_usuario
        devolucao.data_recebimento = datetime.now()
        _aplicar_status(
            db,
            devolucao.entrega,
            "Devolvido",
            id_usuario,
            usuario.nome,
            "Mercadoria devolvida e recebida.",
        )
        _auditar(
            db,
            usuario,
            "RECEBER_DEVOLUCAO",
            "DevolucaoLogistica",
            id_devolucao,
        )
        db.commit()
        db.refresh(devolucao)
        return devolucao
    except Exception:
        db.rollback()
        raise


def listar_entregas(db: Session, status: str | None = None):
    query = db.query(Entrega).order_by(Entrega.id_entrega.asc())
    if status:
        query = query.filter(Entrega.status_logistica == status)
    return query.all()


def listar_historico_entrega(db: Session, id_entrega: int):
    return (
        db.query(EntregaStatusHistorico)
        .filter(EntregaStatusHistorico.id_entrega == id_entrega)
        .order_by(EntregaStatusHistorico.data_hora.desc())
        .all()
    )


def listar_rotas(db: Session, status: str | None = None):
    query = db.query(RotaEntrega).order_by(RotaEntrega.data_planejada.desc())
    if status:
        query = query.filter(RotaEntrega.status_rota == status)
    return query.all()


def listar_devolucoes(db: Session, status: str | None = None):
    query = db.query(DevolucaoLogistica).order_by(
        DevolucaoLogistica.data_solicitacao.desc()
    )
    if status:
        query = query.filter(DevolucaoLogistica.status_devolucao == status)
    return query.all()
