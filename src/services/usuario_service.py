from sqlalchemy.orm import Session

from src.database.models.usuarios import LogOperacao, Perfil, Usuario
from src.services.auth_service import (
    UsuarioAutenticado,
    exigir_permissao,
    registrar_log,
)


def listar_usuarios(db: Session, ator: UsuarioAutenticado) -> list[Usuario]:
    exigir_permissao(ator, "usuarios.gerenciar")
    return db.query(Usuario).order_by(Usuario.nome).all()


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
