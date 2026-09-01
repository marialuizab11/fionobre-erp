# FioNobre ERP - Sistema de Gestão Industrial

ERP acadêmico focado na integração operacional, persistência de dados e apoio à decisão, desenvolvido na disciplina de **Sistemas de Informação e Tecnologias (2026.1)**.

---

## Arquitetura

O sistema segue separação de responsabilidades entre configuração, persistência, regras de negócio e interface Streamlit.

```text
fionobre-erp/
├── config/                 # Variáveis de ambiente e DATABASE_URL
├── src/
│   ├── database/           # ORM SQLAlchemy + conexão PostgreSQL
│   ├── services/           # Regras de negócio
│   └── views/              # Telas Streamlit e componentes de UI
├── .streamlit/             # Tema e secrets OIDC (exemplo versionado)
├── tests/                  # Testes automatizados
├── app.py                  # Entrada da aplicação
├── init_db.py              # Cria tabelas e perfis padrão
├── seed.py                 # Povoamento automático de dados para o BI
├── .env.example             # Modelo de credenciais (sem segredos reais)
├── requirements.txt
└── README.md
```

### Módulos da interface

| Menu | Função |
|---|---|
| Controle de Estoque | Saldos, localizações, ajustes e transferências |
| Pedidos de Venda | Carrinho, orçamento ou confirmação com faturamento/logística |
| Gestão de Vendas | Histórico, conversão de orçamento, cancelamento e Dashboard |
| Contas a Receber | Baixa de pagamentos e acompanhamento financeiro |
| Gestão Logística | Entregas, rotas, rastreio e comprovantes |
| Administração | Usuários, perfis e auditoria (conforme permissões) |

### Ciclo do pedido / orçamento

```text
Orcamento  →  Confirmado  →  Concluído
     │              │
     └──── Cancelado ┘
```

- **Orçamento**: não baixa estoque e não gera financeiro/logística.
- **Confirmado**: baixa estoque e segue o fluxo operacional.
- **Cancelamento**: permitido enquanto não houver pagamento `Pago` e a logística não estiver `Enviado`/`Entregue`.

---

## Como rodar o sistema

### 1. Pré-requisitos

- Python 3.11 ou superior
- PostgreSQL em execução
- Banco criado (exemplo: `fionobre_db`)
- Cliente OAuth Google (login Streamlit)

### 2. Instalação das dependências

```bash
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Variáveis de ambiente

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Edite o `.env`:

```env
DB_USER=postgres
DB_PASSWORD=sua_senha
DB_HOST=localhost
DB_PORT=5432
DB_NAME=fionobre_db
ADMIN_EMAILS=seu_email@gmail.com
```

> O arquivo `.env` não deve ser versionado.

### 4. Login com Google

No Google Cloud, crie um cliente OAuth **Aplicativo da Web** com a URI:

```text
http://localhost:8501/oauth2callback
```

Depois:

```bash
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

Preencha `client_id`, `client_secret` e uma `cookie_secret` longa. Contas novas recebem perfil **Visualizador**; e-mails em `ADMIN_EMAILS` recebem **Administrador**.

### 5. Banco de dados e Avaliação do BI

Para criar as estruturas iniciais do sistema e os perfis padrão, execute:

```bash
python init_db.py
```

> ⚠️ **IMPORTANTE PARA A AVALIAÇÃO:**
> Para testar o módulo analítico (Dashboard) com dados realistas, é necessário popular o banco com o histórico retroativo de 90 dias (Vendas, Compras, Estoque e Financeiro). Execute o comando abaixo:

```bash
python seed.py
```

### 6. Executar o ERP

```bash
streamlit run app.py
```

Abra [http://localhost:8501](http://localhost:8501).

---

## Tecnologias

- Python
- Streamlit (`streamlit[auth]`)
- PostgreSQL
- SQLAlchemy (ORM)
- Python-dotenv

---

## Boas práticas

- Nunca commitar `.env` nem `.streamlit/secrets.toml`
- Credenciais só em variáveis de ambiente / secrets locais
- Justificativa obrigatória (≥ 5 caracteres) no cancelamento

---

## Desenvolvedores

Projeto desenvolvido por:

- [@Maria Luiza Bezerra dos Santos](https://github.com/marialuizab11)
- [@Matheus Cavalcante](https://github.com/Matheuuscavufape)
- [@João Vitor](https://github.com/jvdss3)

## Licença

Uso acadêmico na disciplina Sistemas de Informação e Tecnologias (2026.1).