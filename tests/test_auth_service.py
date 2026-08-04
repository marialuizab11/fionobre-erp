import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base
from src.database.models.usuarios import LogOperacao, Usuario
from src.services.auth_service import criar_contexto_usuario, sincronizar_usuario_google
from src.services.usuario_service import (
    alterar_perfil_usuario,
    alterar_status_usuario,
    cadastrar_usuario,
    listar_logs,
    listar_usuarios,
)


def claims_google(sub: str, email: str, nome: str = "Usuário Teste") -> dict:
    return {
        "sub": sub,
        "email": email,
        "email_verified": True,
        "name": nome,
        "picture": "https://example.com/foto.png",
    }


class AuthServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_usuario_convidado_recebe_perfil_visualizador(self):
        admin = sincronizar_usuario_google(
            self.db,
            claims_google("google-admin", "admin@example.com"),
            admin_emails={"admin@example.com"},
        )
        cadastrar_usuario(
            self.db,
            criar_contexto_usuario(admin),
            "pessoa@example.com",
            "Visualizador",
        )
        usuario = sincronizar_usuario_google(
            self.db,
            claims_google("google-1", "pessoa@example.com"),
        )
        contexto = criar_contexto_usuario(usuario)

        self.assertEqual("Visualizador", contexto.perfil)
        self.assertTrue(contexto.pode("estoque.visualizar"))
        self.assertFalse(contexto.pode("usuarios.gerenciar"))
        self.assertEqual(
            1,
            self.db.query(LogOperacao)
            .filter(
                LogOperacao.acao == "PRIMEIRO_LOGIN",
                LogOperacao.id_usuario == usuario.id_usuario,
            )
            .count(),
        )

    def test_email_configurado_recebe_perfil_administrador(self):
        usuario = sincronizar_usuario_google(
            self.db,
            claims_google("google-admin", "admin@example.com"),
            admin_emails={"admin@example.com"},
        )
        contexto = criar_contexto_usuario(usuario)

        self.assertEqual("Administrador", contexto.perfil)
        self.assertTrue(contexto.pode("usuarios.gerenciar"))
        self.assertTrue(contexto.pode("auditoria.visualizar"))

    def test_administrador_altera_perfil_e_status(self):
        admin = sincronizar_usuario_google(
            self.db,
            claims_google("google-admin", "admin@example.com"),
            admin_emails={"admin@example.com"},
        )
        contexto_admin = criar_contexto_usuario(admin)
        cadastrar_usuario(
            self.db,
            contexto_admin,
            "user@example.com",
            "Visualizador",
        )
        usuario = sincronizar_usuario_google(
            self.db,
            claims_google("google-user", "user@example.com"),
        )

        alterar_perfil_usuario(self.db, contexto_admin, usuario.id_usuario, "Operacional")
        alterar_status_usuario(self.db, contexto_admin, usuario.id_usuario, False)

        atualizado = self.db.get(Usuario, usuario.id_usuario)
        self.assertEqual("Operacional", atualizado.perfil.nome)
        self.assertFalse(atualizado.ativo)
        self.assertEqual(2, len(listar_usuarios(self.db, contexto_admin)))
        self.assertGreaterEqual(len(listar_logs(self.db, contexto_admin)), 4)

    def test_visualizador_nao_gerencia_usuarios(self):
        admin = sincronizar_usuario_google(
            self.db,
            claims_google("google-admin", "admin@example.com"),
            admin_emails={"admin@example.com"},
        )
        cadastrar_usuario(
            self.db,
            criar_contexto_usuario(admin),
            "user@example.com",
            "Visualizador",
        )
        usuario = sincronizar_usuario_google(
            self.db,
            claims_google("google-user", "user@example.com"),
        )
        contexto = criar_contexto_usuario(usuario)

        with self.assertRaises(PermissionError):
            listar_usuarios(self.db, contexto)

    def test_rejeita_usuario_sem_convite(self):
        with self.assertRaises(PermissionError):
            sincronizar_usuario_google(
                self.db,
                claims_google("google-sem-convite", "sem-convite@example.com"),
            )

    def test_rejeita_email_google_nao_verificado(self):
        claims = claims_google("google-2", "pessoa@example.com")
        claims["email_verified"] = False

        with self.assertRaises(ValueError):
            sincronizar_usuario_google(self.db, claims)


if __name__ == "__main__":
    unittest.main()
