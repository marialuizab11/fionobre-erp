from decimal import Decimal

from sqlalchemy.orm import Session

from src.database.models.cadastros import Cliente, Item
from src.database.models.core import MovimentacaoEstoque
from src.database.models.usuarios import Usuario
from src.services.auth_service import UsuarioAutenticado, exigir_permissao, registrar_log


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
