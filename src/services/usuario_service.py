import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.models.usuarios import LogOperacao, Perfil, Permissao, Usuario
from src.services.auth_service import (
    PERFIS_PADRAO,
    PERMISSOES_PADRAO,
    UsuarioAutenticado,
    exigir_permissao,
    registrar_log,
)


PADRAO_CODIGO_PERMISSAO = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")


def _obter_ator(db: Session, ator: UsuarioAutenticado) -> Usuario:
    usuario = db.get(Usuario, ator.id_usuario)
    if usuario is None or not usuario.ativo:
        raise PermissionError("Usuário responsável pela operação é inválido ou está inativo.")
    return usuario


def _perfil_tem_permissao(perfil: Perfil, codigo: str) -> bool:
    return any(permissao.codigo == codigo for permissao in perfil.permissoes)


def _ha_outro_gestor_ativo(db: Session, id_usuario_ignorado: int) -> bool:
    usuarios = (
        db.query(Usuario)
        .filter(Usuario.ativo.is_(True), Usuario.id_usuario != id_usuario_ignorado)
        .all()
    )
    return any(_perfil_tem_permissao(usuario.perfil, "usuarios.gerenciar") for usuario in usuarios)


def _normalizar_nome_perfil(nome: str) -> str:
    nome_normalizado = " ".join((nome or "").strip().split())
    if not nome_normalizado:
        raise ValueError("O nome do perfil é obrigatório.")
    if len(nome_normalizado) > 50:
        raise ValueError("O nome do perfil deve possuir no máximo 50 caracteres.")
    return nome_normalizado


def _normalizar_descricao(descricao: str | None, limite: int = 255) -> str | None:
    valor = " ".join((descricao or "").strip().split()) or None
    if valor and len(valor) > limite:
        raise ValueError(f"A descrição deve possuir no máximo {limite} caracteres.")
    return valor


def _resolver_permissoes(db: Session, codigos: list[str] | set[str]) -> list[Permissao]:
    codigos_normalizados = {str(codigo).strip().lower() for codigo in codigos if str(codigo).strip()}
    if not codigos_normalizados:
        return []

    permissoes = (
        db.query(Permissao)
        .filter(Permissao.codigo.in_(codigos_normalizados))
        .order_by(Permissao.codigo)
        .all()
    )
    encontrados = {permissao.codigo for permissao in permissoes}
    ausentes = sorted(codigos_normalizados - encontrados)
    if ausentes:
        raise ValueError(f"Permissões não encontradas: {', '.join(ausentes)}.")
    return permissoes


def listar_usuarios(db: Session, ator: UsuarioAutenticado) -> list[Usuario]:
    exigir_permissao(ator, "usuarios.gerenciar")
    return db.query(Usuario).order_by(Usuario.nome).all()


def listar_perfis(db: Session, ator: UsuarioAutenticado) -> list[Perfil]:
    exigir_permissao(ator, "usuarios.gerenciar")
    return db.query(Perfil).order_by(Perfil.nome).all()


def listar_permissoes(db: Session, ator: UsuarioAutenticado) -> list[Permissao]:
    exigir_permissao(ator, "usuarios.gerenciar")
    return db.query(Permissao).order_by(Permissao.codigo).all()


def criar_perfil(
    db: Session,
    ator: UsuarioAutenticado,
    nome: str,
    descricao: str | None,
    codigos_permissoes: list[str] | set[str],
) -> Perfil:
    exigir_permissao(ator, "usuarios.gerenciar")
    nome_normalizado = _normalizar_nome_perfil(nome)
    descricao_normalizada = _normalizar_descricao(descricao)

    existente = (
        db.query(Perfil)
        .filter(func.lower(Perfil.nome) == nome_normalizado.lower())
        .first()
    )
    if existente is not None:
        raise ValueError(f"Já existe um perfil chamado '{nome_normalizado}'.")

    try:
        usuario_ator = _obter_ator(db, ator)
        permissoes = _resolver_permissoes(db, codigos_permissoes)
        perfil = Perfil(
            nome=nome_normalizado,
            descricao=descricao_normalizada,
            permissoes=permissoes,
        )
        db.add(perfil)
        db.flush()
        registrar_log(
            db,
            usuario_ator,
            modulo="USUARIOS",
            acao="CRIAR_PERFIL",
            entidade="Perfil",
            id_registro=perfil.id_perfil,
            detalhes={
                "nome": perfil.nome,
                "permissoes": sorted(permissao.codigo for permissao in permissoes),
            },
        )
        db.commit()
        db.refresh(perfil)
        return perfil
    except (ValueError, PermissionError):
        db.rollback()
        raise
    except Exception as erro:
        db.rollback()
        raise RuntimeError(f"Não foi possível criar o perfil: {erro}") from erro


def atualizar_perfil(
    db: Session,
    ator: UsuarioAutenticado,
    id_perfil: int,
    nome: str,
    descricao: str | None,
    codigos_permissoes: list[str] | set[str],
) -> Perfil:
    exigir_permissao(ator, "usuarios.gerenciar")
    perfil = db.get(Perfil, id_perfil)
    if perfil is None:
        raise ValueError("Perfil não encontrado.")

    nome_normalizado = _normalizar_nome_perfil(nome)
    descricao_normalizada = _normalizar_descricao(descricao)
    if perfil.nome in PERFIS_PADRAO and nome_normalizado != perfil.nome:
        raise ValueError("Perfis padrão não podem ser renomeados.")

    duplicado = (
        db.query(Perfil)
        .filter(
            func.lower(Perfil.nome) == nome_normalizado.lower(),
            Perfil.id_perfil != id_perfil,
        )
        .first()
    )
    if duplicado is not None:
        raise ValueError(f"Já existe um perfil chamado '{nome_normalizado}'.")

    try:
        usuario_ator = _obter_ator(db, ator)
        permissoes = _resolver_permissoes(db, codigos_permissoes)
        novos_codigos = {permissao.codigo for permissao in permissoes}
        if (
            usuario_ator.id_perfil == perfil.id_perfil
            and "usuarios.gerenciar" not in novos_codigos
        ):
            raise ValueError(
                "Você não pode retirar a permissão de gerenciar usuários do seu próprio perfil."
            )

        nome_anterior = perfil.nome
        codigos_anteriores = sorted(permissao.codigo for permissao in perfil.permissoes)
        perfil.nome = nome_normalizado
        perfil.descricao = descricao_normalizada
        perfil.permissoes = permissoes
        registrar_log(
            db,
            usuario_ator,
            modulo="USUARIOS",
            acao="ATUALIZAR_PERFIL",
            entidade="Perfil",
            id_registro=perfil.id_perfil,
            detalhes={
                "nome_anterior": nome_anterior,
                "nome": perfil.nome,
                "permissoes_anteriores": codigos_anteriores,
                "permissoes": sorted(novos_codigos),
            },
        )
        db.commit()
        db.refresh(perfil)
        return perfil
    except (ValueError, PermissionError):
        db.rollback()
        raise
    except Exception as erro:
        db.rollback()
        raise RuntimeError(f"Não foi possível atualizar o perfil: {erro}") from erro


def excluir_perfil(
    db: Session,
    ator: UsuarioAutenticado,
    id_perfil: int,
) -> None:
    exigir_permissao(ator, "usuarios.gerenciar")
    perfil = db.get(Perfil, id_perfil)
    if perfil is None:
        raise ValueError("Perfil não encontrado.")
    if perfil.nome in PERFIS_PADRAO:
        raise ValueError("Perfis padrão não podem ser excluídos.")
    if perfil.usuarios:
        raise ValueError("O perfil não pode ser excluído enquanto possuir usuários vinculados.")

    try:
        usuario_ator = _obter_ator(db, ator)
        dados_log = {
            "nome": perfil.nome,
            "permissoes": sorted(permissao.codigo for permissao in perfil.permissoes),
        }
        id_registro = perfil.id_perfil
        db.delete(perfil)
        registrar_log(
            db,
            usuario_ator,
            modulo="USUARIOS",
            acao="EXCLUIR_PERFIL",
            entidade="Perfil",
            id_registro=id_registro,
            detalhes=dados_log,
        )
        db.commit()
    except (ValueError, PermissionError):
        db.rollback()
        raise
    except Exception as erro:
        db.rollback()
        raise RuntimeError(f"Não foi possível excluir o perfil: {erro}") from erro


def criar_permissao(
    db: Session,
    ator: UsuarioAutenticado,
    codigo: str,
    descricao: str,
) -> Permissao:
    exigir_permissao(ator, "usuarios.gerenciar")
    codigo_normalizado = (codigo or "").strip().lower()
    descricao_normalizada = _normalizar_descricao(descricao)
    if not PADRAO_CODIGO_PERMISSAO.fullmatch(codigo_normalizado):
        raise ValueError(
            "Use um código em letras minúsculas, como 'relatorios.exportar'."
        )
    if len(codigo_normalizado) > 100:
        raise ValueError("O código deve possuir no máximo 100 caracteres.")
    if descricao_normalizada is None:
        raise ValueError("A descrição da permissão é obrigatória.")
    if db.query(Permissao).filter(Permissao.codigo == codigo_normalizado).first():
        raise ValueError(f"A permissão '{codigo_normalizado}' já existe.")

    try:
        usuario_ator = _obter_ator(db, ator)
        permissao = Permissao(codigo=codigo_normalizado, descricao=descricao_normalizada)
        db.add(permissao)
        db.flush()
        registrar_log(
            db,
            usuario_ator,
            modulo="USUARIOS",
            acao="CRIAR_PERMISSAO",
            entidade="Permissao",
            id_registro=permissao.id_permissao,
            detalhes={"codigo": permissao.codigo},
        )
        db.commit()
        db.refresh(permissao)
        return permissao
    except (ValueError, PermissionError):
        db.rollback()
        raise
    except Exception as erro:
        db.rollback()
        raise RuntimeError(f"Não foi possível criar a permissão: {erro}") from erro


def atualizar_permissao(
    db: Session,
    ator: UsuarioAutenticado,
    id_permissao: int,
    descricao: str,
) -> Permissao:
    exigir_permissao(ator, "usuarios.gerenciar")
    permissao = db.get(Permissao, id_permissao)
    if permissao is None:
        raise ValueError("Permissão não encontrada.")
    descricao_normalizada = _normalizar_descricao(descricao)
    if descricao_normalizada is None:
        raise ValueError("A descrição da permissão é obrigatória.")

    try:
        usuario_ator = _obter_ator(db, ator)
        descricao_anterior = permissao.descricao
        permissao.descricao = descricao_normalizada
        registrar_log(
            db,
            usuario_ator,
            modulo="USUARIOS",
            acao="ATUALIZAR_PERMISSAO",
            entidade="Permissao",
            id_registro=permissao.id_permissao,
            detalhes={
                "codigo": permissao.codigo,
                "descricao_anterior": descricao_anterior,
                "descricao": permissao.descricao,
            },
        )
        db.commit()
        db.refresh(permissao)
        return permissao
    except (ValueError, PermissionError):
        db.rollback()
        raise
    except Exception as erro:
        db.rollback()
        raise RuntimeError(f"Não foi possível atualizar a permissão: {erro}") from erro


def excluir_permissao(
    db: Session,
    ator: UsuarioAutenticado,
    id_permissao: int,
) -> None:
    exigir_permissao(ator, "usuarios.gerenciar")
    permissao = db.get(Permissao, id_permissao)
    if permissao is None:
        raise ValueError("Permissão não encontrada.")
    if permissao.codigo in PERMISSOES_PADRAO:
        raise ValueError("Permissões usadas pelo sistema não podem ser excluídas.")
    if permissao.perfis:
        raise ValueError("Remova a permissão de todos os perfis antes de excluí-la.")

    try:
        usuario_ator = _obter_ator(db, ator)
        id_registro = permissao.id_permissao
        codigo = permissao.codigo
        db.delete(permissao)
        registrar_log(
            db,
            usuario_ator,
            modulo="USUARIOS",
            acao="EXCLUIR_PERMISSAO",
            entidade="Permissao",
            id_registro=id_registro,
            detalhes={"codigo": codigo},
        )
        db.commit()
    except (ValueError, PermissionError):
        db.rollback()
        raise
    except Exception as erro:
        db.rollback()
        raise RuntimeError(f"Não foi possível excluir a permissão: {erro}") from erro


def listar_logs(
    db: Session,
    ator: UsuarioAutenticado,
    limite: int = 200,
) -> list[LogOperacao]:
    exigir_permissao(ator, "auditoria.visualizar")
    limite_seguro = max(1, min(limite, 1000))
    return (
        db.query(LogOperacao)
        .order_by(LogOperacao.data_hora.desc())
        .limit(limite_seguro)
        .all()
    )


def alterar_perfil_usuario(
    db: Session,
    ator: UsuarioAutenticado,
    id_usuario: int,
    nome_perfil: str,
) -> Usuario:
    exigir_permissao(ator, "usuarios.gerenciar")
    usuario = db.get(Usuario, id_usuario)
    perfil = db.query(Perfil).filter(Perfil.nome == nome_perfil).first()
    usuario_ator = db.get(Usuario, ator.id_usuario)

    if usuario is None:
        raise ValueError("Usuário não encontrado.")
    if perfil is None:
        raise ValueError("Perfil não encontrado.")
    if usuario_ator is None:
        raise PermissionError("Usuário responsável pela operação não encontrado.")
    if (
        usuario.id_usuario == ator.id_usuario
        and not _perfil_tem_permissao(perfil, "usuarios.gerenciar")
    ):
        raise ValueError("Você não pode retirar o próprio acesso administrativo.")
    if (
        usuario.ativo
        and _perfil_tem_permissao(usuario.perfil, "usuarios.gerenciar")
        and not _perfil_tem_permissao(perfil, "usuarios.gerenciar")
        and not _ha_outro_gestor_ativo(db, usuario.id_usuario)
    ):
        raise ValueError("O sistema precisa manter pelo menos um gestor de usuários ativo.")

    perfil_anterior = usuario.perfil.nome
    usuario.perfil = perfil
    registrar_log(
        db,
        usuario_ator,
        modulo="USUARIOS",
        acao="ALTERAR_PERFIL",
        entidade="Usuario",
        id_registro=usuario.id_usuario,
        detalhes={"perfil_anterior": perfil_anterior, "novo_perfil": nome_perfil},
    )
    db.commit()
    db.refresh(usuario)
    return usuario


def alterar_status_usuario(
    db: Session,
    ator: UsuarioAutenticado,
    id_usuario: int,
    ativo: bool,
) -> Usuario:
    exigir_permissao(ator, "usuarios.gerenciar")
    usuario = db.get(Usuario, id_usuario)
    usuario_ator = db.get(Usuario, ator.id_usuario)

    if usuario is None:
        raise ValueError("Usuário não encontrado.")
    if usuario_ator is None:
        raise PermissionError("Usuário responsável pela operação não encontrado.")
    if usuario.id_usuario == ator.id_usuario and not ativo:
        raise ValueError("Você não pode desativar o próprio usuário.")
    if (
        not ativo
        and usuario.ativo
        and _perfil_tem_permissao(usuario.perfil, "usuarios.gerenciar")
        and not _ha_outro_gestor_ativo(db, usuario.id_usuario)
    ):
        raise ValueError("O sistema precisa manter pelo menos um gestor de usuários ativo.")

    usuario.ativo = ativo
    registrar_log(
        db,
        usuario_ator,
        modulo="USUARIOS",
        acao="ATIVAR" if ativo else "DESATIVAR",
        entidade="Usuario",
        id_registro=usuario.id_usuario,
    )
    db.commit()
    db.refresh(usuario)
    return usuario

def cadastrar_usuario(
    db: Session,
    usuario_executor: UsuarioAutenticado,
    email: str,
    nome_perfil: str,
) -> Usuario:
    """
    Pré-cadastra um usuário permitindo que ele faça login posteriormente via Google.
    """
    exigir_permissao(usuario_executor, "usuarios.gerenciar")
    email_normalizado = (email or "").strip().lower()
    if "@" not in email_normalizado or len(email_normalizado) > 240:
        raise ValueError("Informe um e-mail válido com no máximo 240 caracteres.")

    perfil = db.query(Perfil).filter(Perfil.nome == nome_perfil).first()
    if not perfil:
        raise ValueError(f"Perfil '{nome_perfil}' não encontrado.")

    
    usuario_existente = (
        db.query(Usuario)
        .filter(func.lower(Usuario.email) == email_normalizado)
        .first()
    )
    if usuario_existente:
        raise ValueError(f"O e-mail {email_normalizado} já está cadastrado no sistema.")

    try:
        usuario_ator = _obter_ator(db, usuario_executor)
        novo_usuario = Usuario(
            email=email_normalizado,
            nome="Pendente de Primeiro Acesso",
            google_sub=f"PENDENTE_{email_normalizado}",
            id_perfil=perfil.id_perfil,
            ativo=True,
        )
        db.add(novo_usuario)
        db.flush()
        registrar_log(
            db,
            usuario_ator,
            modulo="USUARIOS",
            acao="CONVIDAR_USUARIO",
            entidade="Usuario",
            id_registro=novo_usuario.id_usuario,
            detalhes={"email": email_normalizado, "perfil": perfil.nome},
        )
        db.commit()
        db.refresh(novo_usuario)
        return novo_usuario
    except (ValueError, PermissionError):
        db.rollback()
        raise
    except Exception as erro:
        db.rollback()
        raise RuntimeError(f"Não foi possível cadastrar o usuário: {erro}") from erro
