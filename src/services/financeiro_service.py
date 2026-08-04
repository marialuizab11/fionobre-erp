from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping

from sqlalchemy.orm import Session

from src.database.models.financeiro import (
    DetalheLancamentoFinanceiro,
    LancamentoFinanceiro,
    MovimentoExtratoBancario,
)
from src.database.models.usuarios import Usuario
from src.services.auth_service import (
    UsuarioAutenticado,
    exigir_permissao,
    registrar_log,
)


TIPO_RECEBER = "CONTA_A_RECEBER"
TIPO_PAGAR = "CONTA_A_PAGAR"
STATUS_PENDENTE = "Pendente"
STATUS_PAGO = "Pago"
STATUS_CANCELADO = "Cancelado"

CATEGORIAS_RECEITA = (
    "Vendas",
    "Serviços",
    "Receitas financeiras",
    "Outras receitas",
)
CATEGORIAS_DESPESA = (
    "Compras de materiais",
    "Pessoal",
    "Logística",
    "Impostos",
    "Despesas administrativas",
    "Despesas financeiras",
    "Outras despesas",
)


def _como_datetime(valor: date | datetime, fim_do_dia: bool = False) -> datetime:
    if isinstance(valor, datetime):
        return valor
    return datetime.combine(valor, time.max if fim_do_dia else time.min)


def _valor_positivo(valor: Decimal | float | str) -> Decimal:
    try:
        convertido = Decimal(str(valor)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError) as erro:
        raise ValueError("Informe um valor financeiro válido.") from erro
    if convertido <= 0:
        raise ValueError("O valor do lançamento deve ser maior que zero.")
    return convertido


def _usuario_ator(db: Session, ator: UsuarioAutenticado | None) -> Usuario | None:
    if ator is None:
        return None
    exigir_permissao(ator, "financeiro.gerenciar")
    usuario = db.get(Usuario, ator.id_usuario)
    if usuario is None:
        raise PermissionError("Usuário responsável não encontrado.")
    return usuario


def _adicionar_detalhe(
    lancamento: LancamentoFinanceiro,
    descricao: str,
    categoria: str,
    observacao: str | None = None,
    id_usuario: int | None = None,
) -> None:
    lancamento.detalhe = DetalheLancamentoFinanceiro(
        descricao=descricao.strip(),
        categoria=categoria.strip(),
        observacao=observacao.strip() if observacao else None,
        id_usuario_criacao=id_usuario,
    )


def descricao_lancamento(lancamento: LancamentoFinanceiro) -> str:
    if lancamento.detalhe:
        return lancamento.detalhe.descricao
    if lancamento.id_pedido_venda:
        return f"Venda #{lancamento.id_pedido_venda}"
    if lancamento.id_pedido_compra:
        return f"Compra #{lancamento.id_pedido_compra}"
    return f"Lançamento #{lancamento.id_lancamento}"


def categoria_lancamento(lancamento: LancamentoFinanceiro) -> str:
    if lancamento.detalhe:
        return lancamento.detalhe.categoria
    if lancamento.tipo_lancamento == TIPO_RECEBER:
        return "Vendas"
    return "Compras de materiais"


def criar_conta_a_receber(
    db: Session,
    id_pedido: int,
    valor_total: float,
    data_vencimento: date | datetime,
    id_usuario: int | None = None,
):
    novo_lancamento = LancamentoFinanceiro(
        id_pedido_venda=id_pedido,
        valor=_valor_positivo(valor_total),
        data_vencimento=_como_datetime(data_vencimento),
        tipo_lancamento=TIPO_RECEBER,
        origem_lancamento="venda",
        status_pagamento=STATUS_PENDENTE,
    )
    _adicionar_detalhe(
        novo_lancamento, f"Venda #{id_pedido}", "Vendas", id_usuario=id_usuario
    )
    db.add(novo_lancamento)
    db.commit()
    db.refresh(novo_lancamento)
    return novo_lancamento


def gerar_conta_pagar(
    db: Session,
    id_pedido_compra: int,
    valor_total: float,
    data_vencimento: date | datetime,
    id_usuario: int | None = None,
):
    novo_lancamento = LancamentoFinanceiro(
        id_pedido_compra=id_pedido_compra,
        valor=_valor_positivo(valor_total),
        data_vencimento=_como_datetime(data_vencimento),
        tipo_lancamento=TIPO_PAGAR,
        origem_lancamento="compra",
        status_pagamento=STATUS_PENDENTE,
    )
    _adicionar_detalhe(
        novo_lancamento,
        f"Compra #{id_pedido_compra}",
        "Compras de materiais",
        id_usuario=id_usuario,
    )
    db.add(novo_lancamento)
    return novo_lancamento


def criar_lancamento_manual(
    db: Session,
    ator: UsuarioAutenticado,
    natureza: str,
    descricao: str,
    categoria: str,
    valor: Decimal | float | str,
    data_vencimento: date | datetime,
    observacao: str | None = None,
    data_pagamento: date | datetime | None = None,
) -> LancamentoFinanceiro:
    usuario = _usuario_ator(db, ator)
    natureza_normalizada = natureza.strip().upper()
    if natureza_normalizada not in {"RECEITA", "DESPESA"}:
        raise ValueError("A natureza deve ser RECEITA ou DESPESA.")
    if not descricao.strip():
        raise ValueError("A descrição do lançamento é obrigatória.")
    if not categoria.strip():
        raise ValueError("A categoria do lançamento é obrigatória.")

    pagamento = _como_datetime(data_pagamento) if data_pagamento else None
    lancamento = LancamentoFinanceiro(
        valor=_valor_positivo(valor),
        data_vencimento=_como_datetime(data_vencimento),
        data_pagamento=pagamento,
        tipo_lancamento=(TIPO_RECEBER if natureza_normalizada == "RECEITA" else TIPO_PAGAR),
        origem_lancamento="manual",
        status_pagamento=STATUS_PAGO if pagamento else STATUS_PENDENTE,
    )
    _adicionar_detalhe(
        lancamento,
        descricao,
        categoria,
        observacao=observacao,
        id_usuario=usuario.id_usuario,
    )
    db.add(lancamento)
    db.flush()
    registrar_log(
        db,
        usuario,
        modulo="FINANCEIRO",
        acao="CRIAR_LANCAMENTO_MANUAL",
        entidade="LancamentoFinanceiro",
        id_registro=lancamento.id_lancamento,
        detalhes={
            "natureza": natureza_normalizada,
            "descricao": descricao,
            "categoria": categoria,
            "valor": str(lancamento.valor),
        },
    )
    db.commit()
    db.refresh(lancamento)
    return lancamento


def listar_lancamentos(
    db: Session,
    tipo_lancamento: str | None = TIPO_RECEBER,
    status: str | None = None,
    apenas_vencidas: bool = False,
    data_inicio: date | datetime | None = None,
    data_fim: date | datetime | None = None,
):
    query = db.query(LancamentoFinanceiro)
    if tipo_lancamento:
        query = query.filter(
            LancamentoFinanceiro.tipo_lancamento == tipo_lancamento
        )
    if status:
        query = query.filter(LancamentoFinanceiro.status_pagamento == status)
    if apenas_vencidas:
        query = query.filter(
            LancamentoFinanceiro.status_pagamento == STATUS_PENDENTE,
            LancamentoFinanceiro.data_vencimento < datetime.now(),
        )
    if data_inicio:
        query = query.filter(
            LancamentoFinanceiro.data_vencimento >= _como_datetime(data_inicio)
        )
    if data_fim:
        query = query.filter(
            LancamentoFinanceiro.data_vencimento <= _como_datetime(data_fim, True)
        )
    return query.order_by(LancamentoFinanceiro.data_vencimento.asc()).all()


def registrar_pagamento(
    db: Session,
    id_lancamento: int,
    data_pagamento: date | datetime | None = None,
    ator: UsuarioAutenticado | None = None,
):
    usuario = _usuario_ator(db, ator)
    lancamento = db.get(LancamentoFinanceiro, id_lancamento)
    if not lancamento:
        raise ValueError(f"Lançamento financeiro #{id_lancamento} não encontrado.")
    if lancamento.status_pagamento == STATUS_PAGO:
        raise ValueError("Este lançamento já consta como pago no sistema.")
    if lancamento.status_pagamento == STATUS_CANCELADO:
        raise ValueError("Não é possível baixar um lançamento cancelado.")

    lancamento.status_pagamento = STATUS_PAGO
    lancamento.data_pagamento = _como_datetime(data_pagamento or datetime.now())
    if usuario:
        registrar_log(
            db,
            usuario,
            modulo="FINANCEIRO",
            acao="REGISTRAR_BAIXA",
            entidade="LancamentoFinanceiro",
            id_registro=id_lancamento,
            detalhes={"valor": str(lancamento.valor)},
        )
    try:
        db.commit()
        db.refresh(lancamento)
        return lancamento
    except Exception as erro:
        db.rollback()
        raise RuntimeError(f"Erro ao registrar o pagamento no banco: {erro}") from erro


def cancelar_lancamento_manual(
    db: Session, id_lancamento: int, ator: UsuarioAutenticado
) -> LancamentoFinanceiro:
    usuario = _usuario_ator(db, ator)
    lancamento = db.get(LancamentoFinanceiro, id_lancamento)
    if lancamento is None:
        raise ValueError("Lançamento não encontrado.")
    if lancamento.origem_lancamento != "manual":
        raise ValueError("Somente lançamentos manuais podem ser cancelados por esta tela.")
    if lancamento.status_pagamento == STATUS_PAGO:
        raise ValueError("Um lançamento já pago não pode ser cancelado.")
    lancamento.status_pagamento = STATUS_CANCELADO
    registrar_log(
        db,
        usuario,
        modulo="FINANCEIRO",
        acao="CANCELAR_LANCAMENTO_MANUAL",
        entidade="LancamentoFinanceiro",
        id_registro=id_lancamento,
    )
    db.commit()
    db.refresh(lancamento)
    return lancamento


def cancelar_lancamentos_pedido_compra(db: Session, id_pedido_compra: int):
    lancamentos = db.query(LancamentoFinanceiro).filter(
        LancamentoFinanceiro.id_pedido_compra == id_pedido_compra,
        LancamentoFinanceiro.status_pagamento == STATUS_PENDENTE,
    ).all()
    for lancamento in lancamentos:
        lancamento.status_pagamento = STATUS_CANCELADO


def calcular_fluxo_caixa(
    db: Session,
    data_inicio: date | datetime,
    data_fim: date | datetime,
    incluir_pendentes: bool = False,
) -> dict:
    inicio = _como_datetime(data_inicio)
    fim = _como_datetime(data_fim, True)
    query = db.query(LancamentoFinanceiro).filter(
        LancamentoFinanceiro.status_pagamento != STATUS_CANCELADO
    )
    if not incluir_pendentes:
        query = query.filter(
            LancamentoFinanceiro.status_pagamento == STATUS_PAGO,
            LancamentoFinanceiro.data_pagamento >= inicio,
            LancamentoFinanceiro.data_pagamento <= fim,
        )
    lancamentos = query.all()

    movimentos = []
    entradas = Decimal("0.00")
    saidas = Decimal("0.00")
    for lancamento in lancamentos:
        data_base = lancamento.data_pagamento or lancamento.data_vencimento
        if data_base is None or not inicio <= data_base <= fim:
            continue
        entrada = lancamento.valor if lancamento.tipo_lancamento == TIPO_RECEBER else Decimal("0.00")
        saida = lancamento.valor if lancamento.tipo_lancamento == TIPO_PAGAR else Decimal("0.00")
        entradas += entrada
        saidas += saida
        movimentos.append(
            {
                "id": lancamento.id_lancamento,
                "data": data_base,
                "descricao": descricao_lancamento(lancamento),
                "categoria": categoria_lancamento(lancamento),
                "entrada": entrada,
                "saida": saida,
                "realizado": lancamento.status_pagamento == STATUS_PAGO,
            }
        )
    movimentos.sort(key=lambda item: (item["data"], item["id"]))
    saldo_acumulado = Decimal("0.00")
    for movimento in movimentos:
        saldo_acumulado += movimento["entrada"] - movimento["saida"]
        movimento["saldo"] = saldo_acumulado
    return {
        "movimentos": movimentos,
        "total_entradas": entradas,
        "total_saidas": saidas,
        "saldo": entradas - saidas,
    }


def gerar_balancete(
    db: Session, data_inicio: date | datetime, data_fim: date | datetime
) -> dict:
    lancamentos = listar_lancamentos(
        db, tipo_lancamento=None, data_inicio=data_inicio, data_fim=data_fim
    )
    grupos = defaultdict(
        lambda: {"receitas": Decimal("0.00"), "despesas": Decimal("0.00"), "pendente": Decimal("0.00")}
    )
    for lancamento in lancamentos:
        if lancamento.status_pagamento == STATUS_CANCELADO:
            continue
        grupo = grupos[categoria_lancamento(lancamento)]
        chave = "receitas" if lancamento.tipo_lancamento == TIPO_RECEBER else "despesas"
        grupo[chave] += lancamento.valor
        if lancamento.status_pagamento == STATUS_PENDENTE:
            grupo["pendente"] += lancamento.valor
    linhas = [
        {
            "categoria": categoria,
            **valores,
            "saldo": valores["receitas"] - valores["despesas"],
        }
        for categoria, valores in sorted(grupos.items())
    ]
    return {"linhas": linhas}


def gerar_dre(
    db: Session,
    data_inicio: date | datetime,
    data_fim: date | datetime,
    regime: str = "COMPETENCIA",
) -> dict:
    regime_normalizado = regime.upper()
    if regime_normalizado not in {"COMPETENCIA", "CAIXA"}:
        raise ValueError("Regime inválido para a DRE.")
    inicio = _como_datetime(data_inicio)
    fim = _como_datetime(data_fim, True)
    lancamentos = db.query(LancamentoFinanceiro).filter(
        LancamentoFinanceiro.status_pagamento != STATUS_CANCELADO
    ).all()
    receitas = defaultdict(lambda: Decimal("0.00"))
    despesas = defaultdict(lambda: Decimal("0.00"))
    for lancamento in lancamentos:
        if regime_normalizado == "CAIXA":
            if lancamento.status_pagamento != STATUS_PAGO:
                continue
            data_base = lancamento.data_pagamento
        else:
            data_base = lancamento.data_vencimento
        if data_base is None or not inicio <= data_base <= fim:
            continue
        destino = receitas if lancamento.tipo_lancamento == TIPO_RECEBER else despesas
        destino[categoria_lancamento(lancamento)] += lancamento.valor
    total_receitas = sum(receitas.values(), Decimal("0.00"))
    total_despesas = sum(despesas.values(), Decimal("0.00"))
    return {
        "receitas": dict(sorted(receitas.items())),
        "despesas": dict(sorted(despesas.items())),
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "resultado": total_receitas - total_despesas,
        "regime": regime_normalizado,
    }


def registrar_movimento_extrato(
    db: Session,
    ator: UsuarioAutenticado,
    data_movimento: date | datetime,
    descricao: str,
    valor: Decimal | float | str,
    referencia: str | None = None,
    confirmar: bool = True,
) -> MovimentoExtratoBancario:
    usuario = _usuario_ator(db, ator)
    if not descricao.strip():
        raise ValueError("A descrição do movimento bancário é obrigatória.")
    try:
        valor_decimal = Decimal(str(valor)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError) as erro:
        raise ValueError("Valor inválido no extrato.") from erro
    if valor_decimal == 0:
        raise ValueError("O movimento do extrato não pode ter valor zero.")
    movimento = MovimentoExtratoBancario(
        data_movimento=_como_datetime(data_movimento),
        descricao=descricao.strip(),
        valor=valor_decimal,
        referencia=referencia.strip() if referencia else None,
    )
    db.add(movimento)
    db.flush()
    registrar_log(
        db,
        usuario,
        modulo="FINANCEIRO",
        acao="IMPORTAR_MOVIMENTO_EXTRATO",
        entidade="MovimentoExtratoBancario",
        id_registro=movimento.id_movimento,
        detalhes={"valor": str(valor_decimal), "referencia": referencia},
    )
    if confirmar:
        db.commit()
        db.refresh(movimento)
    return movimento


def importar_movimentos_extrato(
    db: Session,
    ator: UsuarioAutenticado,
    movimentos: Iterable[Mapping],
) -> list[MovimentoExtratoBancario]:
    importados = []
    try:
        for item in movimentos:
            importados.append(
                registrar_movimento_extrato(
                    db,
                    ator,
                    item["data_movimento"],
                    str(item["descricao"]),
                    item["valor"],
                    str(item.get("referencia") or "") or None,
                    confirmar=False,
                )
            )
        db.commit()
        for movimento in importados:
            db.refresh(movimento)
        return importados
    except Exception:
        db.rollback()
        raise


def listar_movimentos_extrato(
    db: Session, apenas_pendentes: bool = False
) -> list[MovimentoExtratoBancario]:
    query = db.query(MovimentoExtratoBancario)
    if apenas_pendentes:
        query = query.filter(MovimentoExtratoBancario.id_lancamento.is_(None))
    return query.order_by(
        MovimentoExtratoBancario.data_movimento.desc(),
        MovimentoExtratoBancario.id_movimento.desc(),
    ).all()


def listar_lancamentos_para_conciliacao(
    db: Session, movimento: MovimentoExtratoBancario | None = None
) -> list[LancamentoFinanceiro]:
    query = db.query(LancamentoFinanceiro).filter(
        LancamentoFinanceiro.status_pagamento != STATUS_CANCELADO,
        ~LancamentoFinanceiro.movimento_extrato.has(),
    )
    if movimento is not None:
        tipo = TIPO_RECEBER if movimento.valor > 0 else TIPO_PAGAR
        query = query.filter(
            LancamentoFinanceiro.tipo_lancamento == tipo,
            LancamentoFinanceiro.valor == abs(movimento.valor),
            LancamentoFinanceiro.data_vencimento >= movimento.data_movimento - timedelta(days=7),
            LancamentoFinanceiro.data_vencimento <= movimento.data_movimento + timedelta(days=7),
        )
    return query.order_by(LancamentoFinanceiro.data_vencimento.desc()).all()


def conciliar_movimento(
    db: Session,
    id_movimento: int,
    id_lancamento: int,
    ator: UsuarioAutenticado,
) -> MovimentoExtratoBancario:
    usuario = _usuario_ator(db, ator)
    movimento = db.get(MovimentoExtratoBancario, id_movimento)
    lancamento = db.get(LancamentoFinanceiro, id_lancamento)
    if movimento is None or lancamento is None:
        raise ValueError("Movimento ou lançamento não encontrado.")
    if movimento.id_lancamento is not None:
        raise ValueError("Este movimento bancário já está conciliado.")
    if lancamento.movimento_extrato is not None:
        raise ValueError("Este lançamento já está conciliado com outro movimento.")
    if lancamento.status_pagamento == STATUS_CANCELADO:
        raise ValueError("Não é possível conciliar um lançamento cancelado.")
    entrada_esperada = lancamento.tipo_lancamento == TIPO_RECEBER
    if (entrada_esperada and movimento.valor < 0) or (
        not entrada_esperada and movimento.valor > 0
    ):
        raise ValueError("A natureza do extrato não corresponde ao lançamento.")
    if abs(movimento.valor) != lancamento.valor:
        raise ValueError("O valor do extrato deve ser igual ao valor do lançamento.")

    movimento.lancamento = lancamento
    movimento.data_conciliacao = datetime.now()
    movimento.id_usuario_conciliacao = usuario.id_usuario
    if lancamento.status_pagamento == STATUS_PENDENTE:
        lancamento.status_pagamento = STATUS_PAGO
        lancamento.data_pagamento = movimento.data_movimento
    registrar_log(
        db,
        usuario,
        modulo="FINANCEIRO",
        acao="CONCILIAR_EXTRATO",
        entidade="MovimentoExtratoBancario",
        id_registro=id_movimento,
        detalhes={"id_lancamento": id_lancamento, "valor": str(movimento.valor)},
    )
    db.commit()
    db.refresh(movimento)
    return movimento
