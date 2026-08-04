import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from sqlalchemy.orm import Session

from src.database.models.usuarios import LogOperacao, Perfil, Permissao, Usuario


PERMISSOES_PADRAO = {
    "cadastros.gerenciar": "Cadastrar clientes e itens",
    "estoque.visualizar": "Visualizar saldos e movimentações de estoque",
    "compras.gerenciar": "Cadastrar fornecedores e gerenciar pedidos de compra",
    "producao.gerenciar": "Cadastrar centros e gerenciar ordens de produção",
    "vendas.gerenciar": "Criar e alterar pedidos de venda",
    "financeiro.gerenciar": "Gerenciar lançamentos, relatórios e conciliação financeira",
    "logistica.gerenciar": "Criar entregas e atualizar seu status",
    "usuarios.gerenciar": "Alterar perfis e situação dos usuários",
    "auditoria.visualizar": "Consultar os logs de operação",
}

PERFIS_PADRAO = {
    "Administrador": set(PERMISSOES_PADRAO),
    "Operacional": {
        "cadastros.gerenciar",
        "estoque.visualizar",
        "compras.gerenciar",
        "producao.gerenciar",
        "vendas.gerenciar",
        "financeiro.gerenciar",
        "logistica.gerenciar",
    },
    "Visualizador": {"estoque.visualizar"},
}


@dataclass(frozen=True)
class UsuarioAutenticado:
    id_usuario: int
    nome: str
    email: str
    foto_url: str | None
    perfil: str
    permissoes: frozenset[str]

    def pode(self, codigo_permissao: str) -> bool:
        return codigo_permissao in self.permissoes


def garantir_perfis_padrao(db: Session) -> None:
    permissoes = {}
    for codigo, descricao in PERMISSOES_PADRAO.items():
        permissao = db.query(Permissao).filter(Permissao.codigo == codigo).first()
        if permissao is None:
            permissao = Permissao(codigo=codigo, descricao=descricao)
            db.add(permissao)
            db.flush()
        permissoes[codigo] = permissao

    for nome, codigos in PERFIS_PADRAO.items():
        perfil = db.query(Perfil).filter(Perfil.nome == nome).first()
        if perfil is None:
            perfil = Perfil(nome=nome, descricao=f"Perfil padrão: {nome}")
            db.add(perfil)
            db.flush()
        perfil.permissoes = [permissoes[codigo] for codigo in sorted(codigos)]


def registrar_log(
    db: Session,
    usuario: Usuario,
    modulo: str,
    acao: str,
    entidade: str | None = None,
    id_registro: int | str | None = None,
    detalhes: Mapping[str, Any] | None = None,
) -> LogOperacao:
    log = LogOperacao(
        id_usuario=usuario.id_usuario,
        modulo=modulo,
        acao=acao,
        entidade=entidade,
        id_registro=str(id_registro) if id_registro is not None else None,
        detalhes=json.dumps(detalhes, ensure_ascii=False, default=str) if detalhes else None,
    )
    db.add(log)
    return log


def sincronizar_usuario_google(
    db: Session,
    claims: Mapping[str, Any],
    admin_emails: set[str] | None = None,
) -> Usuario:
    google_sub = str(claims.get("sub", "")).strip()
    email = str(claims.get("email", "")).strip().lower()
    nome = str(claims.get("name", "")).strip() or email
    foto_url = str(claims.get("picture", "")).strip() or None
    email_verificado = claims.get("email_verified") in (True, "true", "True", 1, "1")

    if not google_sub or not email:
        raise ValueError("O Google não retornou os identificadores obrigatórios do usuário.")
    if not email_verificado:
        raise ValueError("A conta Google precisa possuir um e-mail verificado.")

    garantir_perfis_padrao(db)

    usuario = db.query(Usuario).filter(Usuario.google_sub == google_sub).first()
    if usuario is None:
        if admin_emails and email in admin_emails:
            perfil_admin = db.query(Perfil).filter(Perfil.nome == "Administrador").first()
            
            usuario = Usuario(
                google_sub=google_sub,
                email=email,
                nome=nome,
                foto_url=foto_url,
                ativo=True,
                id_perfil=perfil_admin.id_perfil
            )
            db.add(usuario)
            db.flush()
        else:
            raise PermissionError(
                f"O e-mail '{email}' não está autorizado a acessar o sistema. Solicite um convite ao administrador."
            )

    if usuario is None:
        raise PermissionError(
            f"O e-mail '{email}' não está autorizado a acessar o sistema. Solicite um convite ao administrador."
        )
    
    if not usuario.ativo:
        raise PermissionError("Este usuário está desativado no FioNobre ERP.")

    primeiro_login = usuario.google_sub.startswith("PENDENTE_") or usuario.google_sub != google_sub

    usuario.google_sub = google_sub
    usuario.email = email
    if primeiro_login or usuario.nome == "Pendente de Primeiro Acesso":
        usuario.nome = nome
    usuario.foto_url = foto_url

    usuario.ultimo_login_em = datetime.utcnow()
    
    registrar_log(
        db,
        usuario,
        modulo="AUTENTICACAO",
        acao="PRIMEIRO_LOGIN" if primeiro_login else "LOGIN",
        entidade="Usuario",
        id_registro=usuario.id_usuario,
        detalhes={"email": email, "provedor": "Google"},
    )
    db.commit()
    db.refresh(usuario)
    return usuario


def criar_contexto_usuario(usuario: Usuario) -> UsuarioAutenticado:
    return UsuarioAutenticado(
        id_usuario=usuario.id_usuario,
        nome=usuario.nome,
        email=usuario.email,
        foto_url=usuario.foto_url,
        perfil=usuario.perfil.nome,
        permissoes=frozenset(item.codigo for item in usuario.perfil.permissoes),
    )


def exigir_permissao(usuario: UsuarioAutenticado, codigo_permissao: str) -> None:
    if not usuario.pode(codigo_permissao):
        raise PermissionError(f"Permissão necessária: {codigo_permissao}")