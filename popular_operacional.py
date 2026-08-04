"""Popula cenários idempotentes para testes manuais de produção e logística."""

from datetime import date, timedelta
from decimal import Decimal

from src.database.connection import SessionLocal, engine, init_db
from src.database.models.cadastros import Cliente, Item
from src.database.models.logistica import DevolucaoLogistica, RotaEntrega, Veiculo
from src.database.models.producao import CentroProducao, OrdemProducao
from src.database.models.usuarios import Perfil, Usuario
from src.database.models.vendas import PedidoVenda
from src.services import producao_service
from src.services.auth_service import criar_contexto_usuario
from src.services.cadastro_service import criar_cliente, criar_item
from src.services.estoque_service import entrada_estoque
from src.services.logistica_service import (
    configurar_rastreamento_externo,
    criar_entrega_para_pedido,
    criar_rota_entrega,
    criar_veiculo,
    registrar_comprovante_entrega,
    registrar_evento_rastreamento,
    solicitar_devolucao,
)
from src.services.venda_service import criar_pedido_venda


PREFIXO = "TESTE MANUAL"


def _usuario_administrador(db):
    usuario = (
        db.query(Usuario)
        .join(Usuario.perfil)
        .filter(Usuario.ativo.is_(True), Perfil.nome == "Administrador")
        .order_by(Usuario.id_usuario)
        .first()
    )
    if usuario is None:
        raise RuntimeError(
            "Nenhum administrador ativo foi encontrado. Entre no sistema com a conta "
            "Google administradora e execute este script novamente."
        )
    return usuario, criar_contexto_usuario(usuario)


def _item(db, usuario, descricao, unidade, tipo, saldo, preco=0, custo=0):
    item = db.query(Item).filter(Item.descricao == descricao).first()
    if item is None:
        return criar_item(
            db,
            usuario,
            descricao,
            unidade,
            tipo,
            saldo_inicial=saldo,
            estoque_minimo=20,
            preco_venda=preco,
            custo_medio=custo,
        )
    minimo = Decimal(str(saldo))
    atual = Decimal(str(item.saldo_estoque))
    if atual < minimo:
        entrada_estoque(
            db,
            item.id_item,
            minimo - atual,
            usuario.id_usuario,
            tipo_movimento="ENTRADA_AJUSTE_TESTE",
        )
        db.commit()
        db.refresh(item)
    return item


def _cliente(db, usuario, indice, finalidade):
    documento = f"99000000000{indice:03d}"
    cliente = db.query(Cliente).filter(Cliente.cnpj_cpf == documento).first()
    if cliente:
        return cliente
    return criar_cliente(
        db,
        usuario,
        f"{PREFIXO} - {finalidade}",
        documento,
        email=f"teste{indice}@fionobre.local",
        telefone="81999990000",
        cep=f"50000-{indice:03d}",
        rua=f"Rua de Teste {indice}",
        numero=str(100 + indice),
        bairro="Centro de Testes",
        cidade="Recife",
        uf="PE",
    )


def _entrega_cliente(db, usuario, cliente, produto):
    pedido = (
        db.query(PedidoVenda)
        .filter(PedidoVenda.id_cliente == cliente.id_cliente)
        .order_by(PedidoVenda.id_pedido_venda)
        .first()
    )
    if pedido is None:
        pedido = criar_pedido_venda(
            db,
            cliente.id_cliente,
            [
                {
                    "id_item": produto.id_item,
                    "quantidade": 1,
                    "valor_unitario": produto.preco_venda,
                }
            ],
            usuario,
        )
    if pedido.entrega is None:
        return criar_entrega_para_pedido(
            db,
            pedido.id_pedido_venda,
            date.today() + timedelta(days=3),
            25,
        )
    return pedido.entrega


def _preparar_producao(db, usuario):
    tecido = _item(
        db,
        usuario,
        f"{PREFIXO} - Tecido algodão",
        "M",
        "MATERIA_PRIMA",
        500,
        custo=12,
    )
    linha = _item(
        db,
        usuario,
        f"{PREFIXO} - Linha industrial",
        "UN",
        "INSUMO",
        500,
        custo=4,
    )
    produto = _item(
        db,
        usuario,
        f"{PREFIXO} - Camiseta FioNobre",
        "UN",
        "PRODUTO_ACABADO",
        100,
        preco=79.90,
        custo=25,
    )

    centros = []
    for nome, descricao in (
        (f"{PREFIXO} - Corte", "Centro de corte para demonstração"),
        (f"{PREFIXO} - Costura", "Centro de costura para demonstração"),
    ):
        centro = db.query(CentroProducao).filter(CentroProducao.nome == nome).first()
        if centro is None:
            centro = producao_service.criar_centro_producao(
                db, nome, descricao, usuario.id_usuario
            )
        if centro.capacidade is None:
            producao_service.configurar_capacidade_centro(
                db, centro.id_centro_producao, 8, usuario.id_usuario
            )
        centros.append(centro)

    if producao_service.obter_ficha_tecnica(db, produto.id_item) is None:
        producao_service.salvar_ficha_tecnica(
            db,
            produto.id_item,
            [
                {"id_item_insumo": tecido.id_item, "quantidade_por_unidade": 1.5},
                {"id_item_insumo": linha.id_item, "quantidade_por_unidade": 1},
            ],
            usuario.id_usuario,
            "Ficha para testes manuais de produção.",
        )
    roteiro = producao_service.obter_roteiro_producao(db, produto.id_item)
    if roteiro is None:
        roteiro = producao_service.salvar_roteiro_producao(
            db,
            produto.id_item,
            [
                {
                    "id_centro_producao": centros[0].id_centro_producao,
                    "nome_operacao": "Cortar tecido",
                    "recurso": "Mesa de corte 01",
                    "tempo_setup_horas": 0.5,
                    "tempo_unitario_horas": 0.25,
                    "instrucoes": "Separar moldes e cortar as peças.",
                },
                {
                    "id_centro_producao": centros[1].id_centro_producao,
                    "nome_operacao": "Costurar e finalizar",
                    "recurso": "Máquina de costura 02",
                    "tempo_setup_horas": 1,
                    "tempo_unitario_horas": 0.5,
                    "instrucoes": "Costurar, revisar e embalar.",
                },
            ],
            usuario.id_usuario,
            "Roteiro demonstrativo de corte e costura.",
        )

    ordens = (
        db.query(OrdemProducao)
        .filter(OrdemProducao.id_item_produto == produto.id_item)
        .order_by(OrdemProducao.id_ordem_producao)
        .all()
    )
    while len(ordens) < 2:
        quantidade = 10 if not ordens else 8
        ordem = producao_service.criar_ordem_producao(
            db,
            centros[0].id_centro_producao,
            produto.id_item,
            quantidade,
            usuario.id_usuario,
            data_inicio_planejada=date.today(),
            id_roteiro=roteiro.id_roteiro,
        )
        ordens.append(ordem)
    if all(item.status_ordem != "Em Producao" for item in ordens):
        candidata = next(
            (item for item in reversed(ordens) if item.status_ordem == "Criado"), None
        )
        if candidata:
            producao_service.iniciar_producao(
                db, candidata.id_ordem_producao, usuario.id_usuario
            )
    return produto, ordens


def _preparar_logistica(db, usuario, produto):
    entregas = []
    finalidades = (
        "Rota planejada",
        "Disponível para nova rota",
        "Rastreamento e comprovante",
        "Disponível para devolução",
        "Devolução pendente",
    )
    for indice, finalidade in enumerate(finalidades, start=1):
        cliente = _cliente(db, usuario, indice, finalidade)
        entregas.append(_entrega_cliente(db, usuario, cliente, produto))

    veiculo = db.query(Veiculo).filter(Veiculo.placa == "TES1T01").first()
    if veiculo is None:
        veiculo = criar_veiculo(
            db,
            "TES1T01",
            f"{PREFIXO} - Van de entregas",
            500,
            usuario.id_usuario,
            "Motorista de Teste",
        )
    rota = db.query(RotaEntrega).filter(
        RotaEntrega.descricao == f"{PREFIXO} - Rota Recife"
    ).first()
    if rota is None:
        rota = criar_rota_entrega(
            db,
            f"{PREFIXO} - Rota Recife",
            date.today(),
            veiculo.id_veiculo,
            [{"id_entrega": entregas[0].id_entrega, "peso_estimado_kg": 15}],
            usuario.id_usuario,
        )

    entrega_rastreio = entregas[2]
    if entrega_rastreio.rastreamento is None:
        configurar_rastreamento_externo(
            db,
            entrega_rastreio.id_entrega,
            "TESTE-BR-0001",
            usuario.id_usuario,
            "Transportadora Demonstração",
            "https://example.com/rastreio/TESTE-BR-0001",
        )
    if entrega_rastreio.status_logistica == "Pendente":
        registrar_evento_rastreamento(
            db,
            entrega_rastreio.id_entrega,
            "Enviado",
            usuario.id_usuario,
            "Objeto coletado para demonstração.",
            "Recife/PE",
        )

    for entrega, recebedor in (
        (entregas[3], "Cliente para devolução"),
        (entregas[4], "Cliente com devolução pendente"),
    ):
        if entrega.comprovante is None:
            registrar_comprovante_entrega(
                db,
                entrega.id_entrega,
                recebedor,
                recebedor,
                usuario.id_usuario,
                observacao="Comprovante criado para teste manual.",
            )

    entrega_devolucao = entregas[4]
    devolucao = db.query(DevolucaoLogistica).filter(
        DevolucaoLogistica.id_entrega == entrega_devolucao.id_entrega,
        DevolucaoLogistica.status_devolucao.in_(["SOLICITADA", "EM_TRANSITO"]),
    ).first()
    if devolucao is None and entrega_devolucao.status_logistica != "Devolvido":
        pedido = entrega_devolucao.pedidos[0]
        linha = pedido.itens[0]
        devolucao = solicitar_devolucao(
            db,
            entrega_devolucao.id_entrega,
            "Teste de recebimento de devolução",
            [
                {
                    "id_item": linha.id_item,
                    "quantidade": linha.quantidade_vendida,
                    "condicao_item": "INTEGRO",
                    "reintegrar_estoque": True,
                }
            ],
            usuario.id_usuario,
        )
    return entregas, veiculo, rota, devolucao


def main():
    engine.echo = False
    init_db()
    db = SessionLocal()
    try:
        usuario_db, usuario = _usuario_administrador(db)
        produto, ordens = _preparar_producao(db, usuario)
        entregas, veiculo, rota, devolucao = _preparar_logistica(db, usuario, produto)
        print("Carga de testes manuais concluída.")
        print(f"Usuário responsável: {usuario_db.nome} ({usuario_db.email})")
        print(f"Produto: #{produto.id_item} - {produto.descricao}")
        print(
            "Ordens: "
            + ", ".join(f"#{item.id_ordem_producao} ({item.status_ordem})" for item in ordens)
        )
        print(f"Veículo: #{veiculo.id_veiculo} - {veiculo.placa}")
        print(f"Rota: #{rota.id_rota} ({rota.status_rota})")
        print(
            "Entregas: "
            + ", ".join(f"#{item.id_entrega} ({item.status_logistica})" for item in entregas)
        )
        if devolucao:
            print(
                f"Devolução: #{devolucao.id_devolucao} "
                f"({devolucao.status_devolucao})"
            )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
