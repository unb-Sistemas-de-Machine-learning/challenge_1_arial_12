# Arquitetura do Verificador Científico

## 1. Introdução

### 1.1 Finalidade
Este documento apresenta a arquitetura da solução Verificador Científico, detalhando seus contêineres, o fluxo de processamento de linguagem natural e a topologia de implantação. A modelagem segue o padrão C4 Model para fornecer clareza técnica e estrutural adequada ao escopo.

### 1.2 Escopo
O escopo cobre:
1. Visão lógica da solução baseada nos Níveis 1 (Contexto) e 2 (Contêineres) do C4 Model.
2. Visão de processos e orquestração da inferência de IA.
3. Visão de implementação, refletindo a separação de responsabilidades em código.
4. Visão de implantação da infraestrutura.
5. Visão de dados e persistência.

### 1.3 Definições e Acrônimos
*   **LLM (Large Language Model):** Modelo de linguagem de grande escala utilizado pelos agentes.
*   **MCP (Model Context Protoco l):** Protocolo padronizado para conectar modelos de IA a fontes de dados externas.
*   **BERTopic:** Ferramenta de modelagem de tópicos baseada em transformadores e agrupamento semântico.
*   **API Gateway:** Ponto único de entrada e roteamento para serviços de backend.

---

## 2. Visão Lógica (Modelo C4)

A visão lógica descreve o sistema em níveis crescentes de detalhamento, partindo da interação com o usuário até os serviços executáveis independentes.

### 2.1 Nível 1: Contexto de Sistema
O sistema atua como uma interface de verificação contínua durante a leitura do usuário.
1.  **Usuário:** Leitor que deseja validar a veracidade de um trecho de texto.
2.  **Verificador Científico:** Sistema central que recebe a requisição, orquestra os agentes de IA, consulta fontes acadêmicas e devolve um veredicto fundamentado.
3.  **OpenAlex API:** Sistema externo que fornece o acervo de literatura acadêmica global.

### 2.2 Nível 2: Contêineres
O sistema é segmentado para isolar responsabilidades de interface, orquestração, inteligência e integração.

1.  **Extensão de Navegador (Front-End Service):** Interface estática acionada pelo usuário para selecionar textos e visualizar o JSON de resposta.
2.  **API Gateway (FastAPI):** Orquestrador principal. Aplica rate limiting, roteia a requisição para a esteira autônoma de agentes e registra o feedback.
3.  **Agente Triador (AI Agent):** Recebe a string original e gera variações com o mesmo significado semântico para ampliar a cobertura da busca.
4.  **Agente Pesquisador (Back-End Service):** Gerencia a aquisição de dados repassando as strings para o cache ou para o integrador externo.
5.  **Cache Validator (Cache Server):** Valida buscas recentes para otimizar tempo e custo de tokens.
6.  **Open Alex Tool Search (MCP Server):** Ponte de comunicação estruturada que converte as buscas do agente em requisições para a OpenAlex API.
7.  **BERTopic (Python Service):** Realiza clusterização semântica sobre os abstracts retornados, filtrando ruídos e selecionando uma amostra representativa.
8.  **Agente Juiz (AI Agent):** Recebe os abstracts processados e emite o veredicto final cruzando a alegação inicial com a literatura científica.
9.  **Postgres Database (Database):** Armazena o feedback do usuário (direcionado pelo Gateway) e o histórico de requisições do cache.

### 2.3 Tecnologias e Papéis

| Tecnologia / Contêiner | Papel na Arquitetura |
| :--- | :--- |
| **JavaScript/HTML/CSS** | Interface da Extensão de Navegador |
| **FastAPI (Python)** | API Gateway, roteamento seguro e orquestração |
| **LLMs** | Inteligência dos Agentes Triador e Juiz |
| **Protocolo MCP** | Padronização da ferramenta de busca (Open Alex Tool) |
| **BERTopic (Python)** | Agrupamento semântico e redução de tokens |
| **PostgreSQL** | Persistência relacional para feedback e cache |

---

## 3. Visão de Processos

O fluxo arquitetural ocorre de forma encadeada (esteira de agentes), garantindo processamento em etapas:

1.  A **Extensão** envia o texto selecionado via requisição HTTP para o **API Gateway**.
2.  O Gateway aciona o **Agente Triador** para expandir a string de busca.
3.  O Gateway aciona o **Agente Pesquisador**, que primeiro consulta o **Cache Validator**.
4.  Em caso de *miss* no cache, o Pesquisador aciona o **Open Alex Tool Search (MCP)**.
5.  Os *abstracts* resultantes são processados pelo **BERTopic** para descarte de ruído.
6.  A amostra limpa é enviada ao **Agente Juiz**, que elabora o veredicto.
7.  O Gateway retorna o JSON final para a Extensão e salva, de forma assíncrona, as métricas e feedbacks no **Postgres Database**.

---

## 4. Visão de Implementação

A base de código em backend (Python) está organizada para refletir o desacoplamento dos contêineres e agentes da lógica de negócios:

```text
src/
|- api/
|  |- gateway/           # Rotas do FastAPI, Middlewares, Rate Limiting
|  |- schemas/           # Pydantic models para validação de entrada/saída
|- agents/
|  |- triador.py         # Lógica do Agente Triador (geração de variações)
|  |- pesquisador.py     # Lógica do Agente Pesquisador
|  |- juiz.py            # Lógica do Agente Juiz e formatação do veredicto
|- core/
|  |- config/            # Variáveis de ambiente e chaves de LLMs
|  |- database/          # Conexões PostgreSQL, models e repositórios
|- services/
|  |- bertopic_nlp.py    # Implementação da clusterização de abstracts
|  |- cache.py           # Validador de buscas recentes
|- mcp/
|  |- openalex_tool.py   # Servidor MCP para integração externa
|- tests/
|  |- unit/
|  |- integration/
