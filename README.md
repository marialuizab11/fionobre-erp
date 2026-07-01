FioNobre ERP - Sistema de Gestão Industrial
Este projeto consiste no desenvolvimento de um ERP simplificado focado na integração operacional, persistência de dados e suporte à decisão, desenvolvido como parte da disciplina de Sistemas de Informação e Tecnologias (2026.1).

🏗️ Arquitetura do Sistema
O sistema foi estruturado seguindo o princípio de separação de responsabilidades, garantindo que a lógica de negócio, a persistência de dados e a interface visual sejam modulares e facilmente manteníveis.

Estrutura de Pastas
Plaintext
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
Responsabilidades
database/: Contém o modelo de dados completo do projeto (MER) traduzido para código. É a base de integridade das operações.

services/: O "cérebro" do ERP. Todas as operações integradas (como a baixa de estoque automática ao realizar uma venda) são processadas aqui.

views/: Camada de apresentação. Responsável por capturar os inputs do usuário via Streamlit e exibir os resultados processados.

🚀 Como rodar o sistema
Para configurar o ambiente de desenvolvimento localmente, siga os passos abaixo:

1. Pré-requisitos
Python 3.11+ instalado.

PostgreSQL instalado e em execução.

Um banco de dados criado (ex: fio_nobre_db).

2. Instalação de dependências
Na raiz do projeto, instale as bibliotecas necessárias:

Bash
pip install -r requirements.txt
3. Configuração de Variáveis de Ambiente
O projeto utiliza um arquivo .env para proteger suas credenciais locais.

Na raiz do projeto, copie o arquivo de exemplo:

Bash
cp .env.example .env
Edite o arquivo .env criado com as credenciais do seu banco de dados local:

Plaintext
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
DB_HOST=localhost
DB_PORT=5432
DB_NAME=fio_nobre_db
4. Inicialização do Banco de Dados
Para garantir que as tabelas existam no seu banco de dados local, execute o script de inicialização pela primeira vez:

Bash
python teste_banco.py
5. Executando o ERP
Para iniciar a aplicação Streamlit:

Bash
streamlit run app.py
Desenvolvido por: Maria Luiza Bezerra dos Santos e equipe.

Dica para o Git
Note que o arquivo .env foi adicionado ao .gitignore para evitar o compartilhamento acidental de senhas. Nunca suba o seu arquivo .env com senhas reais para o repositório.