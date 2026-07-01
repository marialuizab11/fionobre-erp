# 🏭 FioNobre ERP - Sistema de Gestão Industrial

Este projeto consiste no desenvolvimento de um **ERP simplificado** focado na integração operacional, persistência de dados e suporte à decisão, desenvolvido como parte da disciplina de **Sistemas de Informação e Tecnologias (2026.1)**.

---

# 🏗️ Arquitetura do Sistema

O sistema foi estruturado seguindo o princípio de **separação de responsabilidades**, garantindo que a lógica de negócio, a persistência de dados e a interface visual sejam modulares e facilmente manteníveis.

## 📂 Estrutura de Pastas

```text
fionobre-erp/
├── config/              # Configurações globais e carregamento de variáveis de ambiente
├── src/
│   ├── database/        # Camada de Dados: Mapeamento ORM e conexão com PostgreSQL
│   ├── services/        # Regras de Negócio: Lógica de faturamento, estoque e fluxos
│   └── views/           # Interface (UI): Telas e menus construídos em Streamlit
├── app.py               # Ponto de entrada do sistema
├── .env.example         # Template de configuração de ambiente
├── requirements.txt     # Dependências do projeto
└── README.md            # Documentação do projeto
```

## 📋 Responsabilidades

### 📁 `database/`

Contém o modelo de dados completo do projeto (MER) traduzido para código. É responsável pela persistência das informações e pela integridade das operações realizadas no sistema.

### ⚙️ `services/`

Representa o **cérebro do ERP**. Toda a lógica de negócio é implementada nesta camada, incluindo processos integrados, como:

- Baixa automática de estoque após uma venda;
- Processamento de faturamento;
- Validação de regras de negócio;
- Fluxos operacionais do sistema.

### 🖥️ `views/`

Camada de apresentação da aplicação. Responsável por:

- Capturar os dados inseridos pelo usuário;
- Exibir informações e resultados;
- Construir toda a interface utilizando **Streamlit**.

---

# 🚀 Como rodar o sistema

## 1️⃣ Pré-requisitos

Antes de iniciar, certifique-se de possuir:

- Python **3.11** ou superior;
- PostgreSQL instalado e em execução;
- Um banco de dados criado (exemplo: `fio_nobre_db`).

---

## 2️⃣ Instalação das dependências

Na raiz do projeto, execute:

```bash
pip install -r requirements.txt
```

---

## 3️⃣ Configuração das variáveis de ambiente

O projeto utiliza um arquivo `.env` para armazenar as credenciais do banco de dados.

Primeiro, copie o arquivo de exemplo:

```bash
cp .env.example .env
```

Depois, edite o arquivo `.env` preenchendo as informações do seu banco:

```env
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
DB_HOST=localhost
DB_PORT=5432
DB_NAME=fio_nobre_db
```

---

## 4️⃣ Inicialização do banco de dados

Na primeira execução, crie as tabelas do banco executando:

```bash
python teste_banco.py
```

---

## 5️⃣ Executando o ERP

Inicie a aplicação com o Streamlit:

```bash
streamlit run app.py
```

Após a execução, o sistema estará disponível no navegador.

---

# 👨‍💻 Tecnologias Utilizadas

- Python
- Streamlit
- PostgreSQL
- SQLAlchemy (ORM)
- Python-dotenv
- Git e GitHub

---

# 🔒 Boas práticas

> **Importante:** O arquivo `.env` está listado no `.gitignore` para impedir o compartilhamento de informações sensíveis.

**Nunca envie seu arquivo `.env` para o GitHub**, pois ele contém credenciais do banco de dados.

Utilize apenas o arquivo **`.env.example`** para servir como modelo de configuração.

---

# 👥 Desenvolvedores

Projeto desenvolvido por:
 _pendente_

---

## 📄 Licença

Este projeto foi desenvolvido para fins acadêmicos na disciplina de **Sistemas de Informação e Tecnologias (2026.1)**.
