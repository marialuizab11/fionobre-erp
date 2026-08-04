from decimal import Decimal
from sqlalchemy.orm import Session

from src.database.models.cadastros import Cliente, Item
from src.database.models.compras import  Fornecedor
from src.database.models.core import MovimentacaoEstoque
from src.database.models.usuarios import Usuario
from src.database.models.vendas import PedidoVenda
from src.services.auth_service import UsuarioAutenticado, exigir_permissao, registrar_log

def listar_clientes(db: Session) -> list[Cliente]:
    return db.query(Cliente).order_by(Cliente.razao_social.asc()).all()


def criar_cliente(
    db: Session,
    usuario: UsuarioAutenticado,
    razao_social: str,
    cnpj_cpf: str,
    **dados,
) -> Cliente:
    exigir_permissao(usuario, "cadastros.gerenciar")
    razao_social = razao_social.strip()
    cnpj_cpf = cnpj_cpf.strip()
    if not razao_social or not cnpj_cpf:
        raise ValueError("Nome/razão social e CPF/CNPJ são obrigatórios.")

    try:
        if db.query(Cliente).filter(Cliente.cnpj_cpf == cnpj_cpf).first():
            raise ValueError("Já existe um cliente com este CPF/CNPJ.")
        usuario_db = db.get(Usuario, usuario.id_usuario)
        if usuario_db is None or not usuario_db.ativo:
            raise PermissionError("Usuário responsável inválido ou inativo.")

        cliente = Cliente(
            razao_social=razao_social,
            cnpj_cpf=cnpj_cpf,
            email=(dados.get("email") or "").strip() or None,
            telefone=(dados.get("telefone") or "").strip() or None,
            cep=(dados.get("cep") or "").strip() or None,
            rua=(dados.get("rua") or "").strip() or None,
            numero=(dados.get("numero") or "").strip() or None,
            bairro=(dados.get("bairro") or "").strip() or None,
            cidade=(dados.get("cidade") or "").strip() or None,
            uf=(dados.get("uf") or "").strip().upper() or None,
        )
        db.add(cliente)
        db.flush()
        registrar_log(
            db,
            usuario_db,
            modulo="CADASTROS",
            acao="CRIAR_CLIENTE",
            entidade="Cliente",
            id_registro=cliente.id_cliente,
        )
        db.commit()
        db.refresh(cliente)
        return cliente
    except (ValueError, PermissionError):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def editar_cliente(
    db: Session,
    usuario: UsuarioAutenticado,
    id_cliente: int,
    razao_social: str,
    cnpj_cpf: str,
    **dados,
) -> Cliente:
    exigir_permissao(usuario, "cadastros.gerenciar")
    cliente = db.get(Cliente, id_cliente)
    if not cliente:
        raise ValueError(f"Cliente #{id_cliente} não encontrado.")

    razao_social = razao_social.strip()
    cnpj_cpf = cnpj_cpf.strip()
    if not razao_social or not cnpj_cpf:
        raise ValueError("Nome/razão social e CPF/CNPJ são obrigatórios.")

    try:
        existente = db.query(Cliente).filter(Cliente.cnpj_cpf == cnpj_cpf, Cliente.id_cliente != id_cliente).first()
        if existente:
            raise ValueError("Já existe outro cliente cadastrado com este CPF/CNPJ.")

        usuario_db = db.get(Usuario, usuario.id_usuario)

        cliente.razao_social = razao_social
        cliente.cnpj_cpf = cnpj_cpf
        cliente.email = (dados.get("email") or "").strip() or None
        cliente.telefone = (dados.get("telefone") or "").strip() or None
        cliente.cep = (dados.get("cep") or "").strip() or None
        cliente.rua = (dados.get("rua") or "").strip() or None
        cliente.numero = (dados.get("numero") or "").strip() or None
        cliente.bairro = (dados.get("bairro") or "").strip() or None
        cliente.cidade = (dados.get("cidade") or "").strip() or None
        cliente.uf = (dados.get("uf") or "").strip().upper() or None

        registrar_log(
            db,
            usuario_db,
            modulo="CADASTROS",
            acao="EDITAR_CLIENTE",
            entidade="Cliente",
            id_registro=cliente.id_cliente,
        )
        db.commit()
        db.refresh(cliente)
        return cliente
    except (ValueError, PermissionError):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def remover_cliente(db: Session, usuario: UsuarioAutenticado, id_cliente: int) -> None:
    exigir_permissao(usuario, "cadastros.gerenciar")
    cliente = db.get(Cliente, id_cliente)
    if not cliente:
        raise ValueError(f"Cliente #{id_cliente} não encontrado.")

    # Verifica se existem pedidos de venda associados ao cliente
    tem_pedidos = db.query(PedidoVenda).filter(PedidoVenda.id_cliente == id_cliente).first()
    if tem_pedidos:
        raise ValueError("Este cliente possui pedidos de venda vinculados e não pode ser excluído.")

    try:
        usuario_db = db.get(Usuario, usuario.id_usuario)
        registrar_log(
            db,
            usuario_db,
            modulo="CADASTROS",
            acao="REMOVER_CLIENTE",
            entidade="Cliente",
            id_registro=cliente.id_cliente,
            detalhes={"razao_social": cliente.razao_social, "cnpj_cpf": cliente.cnpj_cpf},
        )
        db.delete(cliente)
        db.commit()
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Erro ao remover o cliente: {e}")

def listar_itens(db: Session) -> list[Item]:
    return db.query(Item).order_by(Item.descricao.asc()).all()


def criar_item(
    db: Session,
    usuario: UsuarioAutenticado,
    descricao: str,
    unidade_medida: str,
    tipo_item: str,
    saldo_inicial=0,
    estoque_minimo=0,
    preco_venda=0,
    custo_medio=0,
) -> Item:
    exigir_permissao(usuario, "cadastros.gerenciar")
    descricao = descricao.strip()
    saldo = Decimal(str(saldo_inicial))
    minimo = Decimal(str(estoque_minimo))
    preco = Decimal(str(preco_venda))
    custo = Decimal(str(custo_medio))

    if not descricao or not unidade_medida or not tipo_item:
        raise ValueError("Descrição, unidade e tipo do item são obrigatórios.")
    if min(saldo, minimo, preco, custo) < 0:
        raise ValueError("Saldo, estoque mínimo, preço e custo não podem ser negativos.")

    try:
        usuario_db = db.get(Usuario, usuario.id_usuario)
        if usuario_db is None or not usuario_db.ativo:
            raise PermissionError("Usuário responsável inválido ou inativo.")

        item = Item(
            descricao=descricao,
            saldo_estoque=saldo,
            estoque_minimo=minimo,
            preco_venda=preco,
            custo_medio=custo,
            unidade_medida=unidade_medida,
            tipo_item=tipo_item,
        )
        db.add(item)
        db.flush()
        if saldo > 0:
            db.add(
                MovimentacaoEstoque(
                    id_item=item.id_item,
                    id_usuario=usuario.id_usuario,
                    quantidade=saldo,
                    tipo_movimento="SALDO_INICIAL",
                )
            )
        registrar_log(
            db,
            usuario_db,
            modulo="CADASTROS",
            acao="CRIAR_ITEM",
            entidade="Item",
            id_registro=item.id_item,
            detalhes={"saldo_inicial": saldo, "tipo_item": tipo_item},
        )
        db.commit()
        db.refresh(item)
        return item
    except (ValueError, PermissionError):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def editar_item(
    db: Session,
    usuario: UsuarioAutenticado,
    id_item: int,
    descricao: str,
    unidade_medida: str,
    tipo_item: str,
    estoque_minimo=0,
    preco_venda=0,
    custo_medio=0,
) -> Item:
    exigir_permissao(usuario, "cadastros.gerenciar")
    item = db.get(Item, id_item)
    if not item:
        raise ValueError(f"Item #{id_item} não encontrado.")

    descricao = descricao.strip()
    minimo = Decimal(str(estoque_minimo))
    preco = Decimal(str(preco_venda))
    custo = Decimal(str(custo_medio))

    if not descricao or not unidade_medida or not tipo_item:
        raise ValueError("Descrição, unidade e tipo do item são obrigatórios.")
    if min(minimo, preco, custo) < 0:
        raise ValueError("Estoque mínimo, preço e custo não podem ser negativos.")

    try:
        usuario_db = db.get(Usuario, usuario.id_usuario)

        item.descricao = descricao
        item.unidade_medida = unidade_medida
        item.tipo_item = tipo_item
        item.estoque_minimo = minimo
        item.preco_venda = preco
        item.custo_medio = custo

        registrar_log(
            db,
            usuario_db,
            modulo="CADASTROS",
            acao="EDITAR_ITEM",
            entidade="Item",
            id_registro=item.id_item,
        )
        db.commit()
        db.refresh(item)
        return item
    except (ValueError, PermissionError):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def remover_item(db: Session, usuario: UsuarioAutenticado, id_item: int) -> None:
    exigir_permissao(usuario, "cadastros.gerenciar")
    item = db.get(Item, id_item)
    if not item:
        raise ValueError(f"Item #{id_item} não encontrado.")

    try:
        usuario_db = db.get(Usuario, usuario.id_usuario)
        registrar_log(
            db,
            usuario_db,
            modulo="CADASTROS",
            acao="REMOVER_ITEM",
            entidade="Item",
            id_registro=item.id_item,
            detalhes={"descricao": item.descricao},
        )
        db.delete(item)
        db.commit()
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Não foi possível remover o item. Ele pode ter vendas ou movimentações associadas: {e}")


def listar_fornecedores(db: Session) -> list[Fornecedor]:
    return db.query(Fornecedor).order_by(Fornecedor.razao_social.asc()).all()


def criar_fornecedor(
    db: Session,
    usuario: UsuarioAutenticado,
    razao_social: str,
    cnpj: str,
    **dados,
) -> Fornecedor:
    exigir_permissao(usuario, "cadastros.gerenciar")
    razao_social = razao_social.strip()
    cnpj = cnpj.strip()

    if not razao_social or not cnpj:
        raise ValueError("Razão social e CNPJ são obrigatórios.")

    try:
        if db.query(Fornecedor).filter(Fornecedor.cnpj == cnpj).first():
            raise ValueError("Já existe um fornecedor com este CNPJ.")

        usuario_db = db.get(Usuario, usuario.id_usuario)

        fornecedor = Fornecedor(
            razao_social=razao_social,
            cnpj=cnpj,
            nome_fantasia=(dados.get("nome_fantasia") or "").strip() or None,
            email=(dados.get("email") or "").strip() or None,
            telefone=(dados.get("telefone") or "").strip() or None,
        )
        db.add(fornecedor)
        db.flush()
        registrar_log(
            db,
            usuario_db,
            modulo="CADASTROS",
            acao="CRIAR_FORNECEDOR",
            entidade="Fornecedor",
            id_registro=fornecedor.id_fornecedor,
        )
        db.commit()
        db.refresh(fornecedor)
        return fornecedor
    except (ValueError, PermissionError):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def editar_fornecedor(
    db: Session,
    usuario: UsuarioAutenticado,
    id_fornecedor: int,
    razao_social: str,
    cnpj: str,
    **dados,
) -> Fornecedor:
    exigir_permissao(usuario, "cadastros.gerenciar")
    fornecedor = db.get(Fornecedor, id_fornecedor)
    if not fornecedor:
        raise ValueError(f"Fornecedor #{id_fornecedor} não encontrado.")

    razao_social = razao_social.strip()
    cnpj = cnpj.strip()
    if not razao_social or not cnpj:
        raise ValueError("Razão social e CNPJ são obrigatórios.")

    try:
        existente = db.query(Fornecedor).filter(Fornecedor.cnpj == cnpj, Fornecedor.id_fornecedor != id_fornecedor).first()
        if existente:
            raise ValueError("Já existe outro fornecedor cadastrado com este CNPJ.")

        usuario_db = db.get(Usuario, usuario.id_usuario)

        fornecedor.razao_social = razao_social
        fornecedor.cnpj = cnpj
        fornecedor.nome_fantasia = (dados.get("nome_fantasia") or "").strip() or None
        fornecedor.email = (dados.get("email") or "").strip() or None
        fornecedor.telefone = (dados.get("telefone") or "").strip() or None

        registrar_log(
            db,
            usuario_db,
            modulo="CADASTROS",
            acao="EDITAR_FORNECEDOR",
            entidade="Fornecedor",
            id_registro=fornecedor.id_fornecedor,
        )
        db.commit()
        db.refresh(fornecedor)
        return fornecedor
    except (ValueError, PermissionError):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def remover_fornecedor(db: Session, usuario: UsuarioAutenticado, id_fornecedor: int) -> None:
    exigir_permissao(usuario, "cadastros.gerenciar")
    fornecedor = db.get(Fornecedor, id_fornecedor)
    if not fornecedor:
        raise ValueError(f"Fornecedor #{id_fornecedor} não encontrado.")

    try:
        usuario_db = db.get(Usuario, usuario.id_usuario)
        registrar_log(
            db,
            usuario_db,
            modulo="CADASTROS",
            acao="REMOVER_FORNECEDOR",
            entidade="Fornecedor",
            id_registro=fornecedor.id_fornecedor,
            detalhes={"razao_social": fornecedor.razao_social, "cnpj": fornecedor.cnpj},
        )
        db.delete(fornecedor)
        db.commit()
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Não foi possível remover o fornecedor. Ele pode ter pedidos de compra associados: {e}")