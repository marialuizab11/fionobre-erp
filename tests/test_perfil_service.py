import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base
from src.database.models.usuarios import LogOperacao, Perfil, Permissao
from src.services.auth_service import (
    carregar_contexto_usuario,
    criar_contexto_usuario,
    garantir_perfis_padrao,
    sincronizar_usuario_google,
)
from src.services.usuario_service import (
    atualizar_perfil,
    atualizar_permissao,
    cadastrar_usuario,
    criar_perfil,
    criar_permissao,
    excluir_perfil,
    excluir_permissao,
    listar_perfis,
    listar_permissoes,
)


def claims_google(sub: str, email: str) -> dict:
    return {
        "sub": sub,
        "email": email,
        "email_verified": True,
        "name": "Administrador de Acesso",
    }


class PerfilServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        usuario = sincronizar_usuario_google(
            self.db,
            claims_google("admin-perfis", "admin-perfis@example.com"),
            admin_emails={"admin-perfis@example.com"},
        )
        self.admin = criar_contexto_usuario(usuario)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_cria_e_edita_perfil_e_permissao_com_auditoria(self):
        permissao = criar_permissao(
            self.db,
            self.admin,
            "relatorios.exportar",
            "Exportar relatórios",
        )
        perfil = criar_perfil(
            self.db,
            self.admin,
            "Analista",
            "Acesso aos relatórios",
            ["estoque.visualizar", permissao.codigo],
        )

        atualizado = atualizar_perfil(
            self.db,
            self.admin,
            perfil.id_perfil,
            "Analista ERP",
            "Perfil personalizado",
            [permissao.codigo],
        )
        permissao_atualizada = atualizar_permissao(
            self.db,
            self.admin,
            permissao.id_permissao,
            "Exportar relatórios em arquivos",
        )

        self.assertEqual("Analista ERP", atualizado.nome)
        self.assertEqual(
            {"relatorios.exportar"},
            {item.codigo for item in atualizado.permissoes},
        )
        self.assertEqual(
            "Exportar relatórios em arquivos",
            permissao_atualizada.descricao,
        )
        acoes = {
            log.acao
            for log in self.db.query(LogOperacao)
            .filter(LogOperacao.modulo == "USUARIOS")
            .all()
        }
        self.assertTrue(
            {"CRIAR_PERFIL", "ATUALIZAR_PERFIL", "CRIAR_PERMISSAO"}.issubset(acoes)
        )

    def test_seed_nao_sobrescreve_permissoes_personalizadas(self):
        administrador = (
            self.db.query(Perfil).filter(Perfil.nome == "Administrador").one()
        )
        codigos = {
            item.codigo
            for item in administrador.permissoes
            if item.codigo != "auditoria.visualizar"
        }
        atualizar_perfil(
            self.db,
            self.admin,
            administrador.id_perfil,
            administrador.nome,
            administrador.descricao,
            codigos,
        )

        garantir_perfis_padrao(self.db)
        self.db.commit()
        self.db.expire_all()
        administrador = self.db.get(Perfil, administrador.id_perfil)

        self.assertNotIn(
            "auditoria.visualizar",
            {item.codigo for item in administrador.permissoes},
        )
        self.assertIn(
            "usuarios.gerenciar",
            {item.codigo for item in administrador.permissoes},
        )
        contexto_atualizado = carregar_contexto_usuario(
            self.db,
            self.admin.id_usuario,
        )
        self.assertFalse(contexto_atualizado.pode("auditoria.visualizar"))

    def test_bloqueia_retirada_do_proprio_acesso_administrativo(self):
        administrador = (
            self.db.query(Perfil).filter(Perfil.nome == "Administrador").one()
        )
        codigos_sem_gestao = {
            item.codigo
            for item in administrador.permissoes
            if item.codigo != "usuarios.gerenciar"
        }

        with self.assertRaisesRegex(ValueError, "próprio perfil"):
            atualizar_perfil(
                self.db,
                self.admin,
                administrador.id_perfil,
                administrador.nome,
                administrador.descricao,
                codigos_sem_gestao,
            )

    def test_exclusao_respeita_perfis_em_uso_e_permissoes_do_sistema(self):
        perfil = criar_perfil(
            self.db,
            self.admin,
            "Temporário",
            None,
            ["estoque.visualizar"],
        )
        cadastrar_usuario(
            self.db,
            self.admin,
            "temporario@example.com",
            perfil.nome,
        )

        with self.assertRaisesRegex(ValueError, "usuários vinculados"):
            excluir_perfil(self.db, self.admin, perfil.id_perfil)

        permissao_sistema = (
            self.db.query(Permissao)
            .filter(Permissao.codigo == "estoque.visualizar")
            .one()
        )
        with self.assertRaisesRegex(ValueError, "usadas pelo sistema"):
            excluir_permissao(self.db, self.admin, permissao_sistema.id_permissao)

        permissao_livre = criar_permissao(
            self.db,
            self.admin,
            "teste.remover",
            "Permissão temporária",
        )
        excluir_permissao(self.db, self.admin, permissao_livre.id_permissao)
        self.assertIsNone(self.db.get(Permissao, permissao_livre.id_permissao))

    def test_visualizador_nao_gerencia_perfis(self):
        cadastrar_usuario(
            self.db,
            self.admin,
            "viewer-perfis@example.com",
            "Visualizador",
        )
        usuario = sincronizar_usuario_google(
            self.db,
            claims_google("viewer-perfis", "viewer-perfis@example.com"),
        )
        visualizador = criar_contexto_usuario(usuario)

        with self.assertRaises(PermissionError):
            listar_perfis(self.db, visualizador)
        with self.assertRaises(PermissionError):
            listar_permissoes(self.db, visualizador)


if __name__ == "__main__":
    unittest.main()
