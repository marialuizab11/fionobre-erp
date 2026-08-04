from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session

from src.database.models.cadastros import Item
from src.database.models.estoque import InventarioFisico, ItemInventario, EstoqueLocalizacao
from src.services.estoque_service import ajustar_estoque_manual


def iniciar_inventario(db: Session, id_localizacao: int, id_usuario: int, observacoes: str = None) -> InventarioFisico:
    """Inicia um novo inventário, congelando o saldo atual dos itens daquela localização."""
    aberto = db.query(InventarioFisico).filter(InventarioFisico.status == "ABERTO").first()
    if aberto:
        raise ValueError("Já existe um inventário físico em andamento.")

    novo_inv = InventarioFisico(
        status="ABERTO",
        id_usuario=id_usuario,
        observacoes=observacoes
    )
    db.add(novo_inv)
    db.flush()

    itens = db.query(Item).all()
    for item in itens:
        saldo_atual = Decimal("0.00")
        est_loc = db.query(EstoqueLocalizacao).filter(
            EstoqueLocalizacao.id_item == item.id_item,
            EstoqueLocalizacao.id_localizacao == id_localizacao
        ).first()
        
        if est_loc:
            saldo_atual = est_loc.quantidade

        item_inv = ItemInventario(
            id_inventario=novo_inv.id_inventario,
            id_item=item.id_item,
            id_localizacao=id_localizacao,
            quantidade_sistema=saldo_atual,
            quantidade_contada=saldo_atual
        )
        db.add(item_inv)

    db.commit()
    db.refresh(novo_inv)
    return novo_inv


def processar_contagem(db: Session, dados_contagem: list):
    """Recebe as quantidades contadas na tela e salva temporariamente nos registros."""
    for dc in dados_contagem:
        linha = db.get(ItemInventario, dc["id_item_inventario"])
        if linha:
            linha.quantidade_contada = Decimal(str(dc["quantidade_contada"]))
    db.commit()


def finalizar_inventario(db: Session, id_inventario: int, id_usuario: int):
    """Calcula divergências, aplica ajustes manuais e conclui o inventário."""
    inventario = db.get(InventarioFisico, id_inventario)
    if not inventario or inventario.status != "ABERTO":
        raise ValueError("Inventário não encontrado ou já finalizado.")

    for linha in inventario.itens:
        contada = linha.quantidade_contada if linha.quantidade_contada is not None else linha.quantidade_sistema
        diferenca = contada - linha.quantidade_sistema
        
        linha.diferenca = diferenca

        if diferenca != 0:
            ajustar_estoque_manual(
                db=db,
                id_item=linha.id_item,
                id_localizacao=linha.id_localizacao,
                quantidade_ajuste=float(diferenca),
                id_usuario=id_usuario,
                observacao=f"Ajuste via Inventário Físico #{inventario.id_inventario}"
            )

    inventario.status = "CONCLUIDO"
    inventario.data_conclusao = datetime.utcnow()
    db.commit()
    db.refresh(inventario)
    return inventario