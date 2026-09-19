# 006 — Configuração centralizada do backend

| Campo | Valor |
| :--- | :--- |
| **Status** | em revisão |
| **Autor** | a definir |
| **Branch** | `feature/006-configuracao-centralizada` |
| **Depende de** | — |
| **Origem** | [Task #6](https://github.com/unb-Sistemas-de-Machine-learning/challenge_1_arial_12/issues/6) |

---

## 1. Objetivo

Garantir que o backend receba sua configuração de um único lugar e avise, já na inicialização, quando faltar uma configuração obrigatória. Chaves sensíveis não devem aparecer em mensagens de erro ou logs.

## 2. Contexto

Esta feature atende ao **API Gateway (FastAPI)** da [arquitetura](../../docs/pages/arquitetura.md). Antes desta entrega, `verificador/backend/src/core/config/settings.py` estava vazio e o stub em `verificador/backend/main.py` configurava a aplicação diretamente. O `.env.example` documentava `APP_DEBUG`, `OPENAI_API_KEY`, `DATABASE_URL` e `OPENALEX_MAILTO`; esta entrega acrescenta `CORS_ORIGINS` à configuração e ao exemplo de ambiente.

Nesta proposta, `DATABASE_URL` é obrigatória e não pode estar vazia ou conter somente espaços. `APP_DEBUG` tem valor padrão `false`; `OPENAI_API_KEY` e `OPENALEX_MAILTO` permanecem opcionais enquanto o stub não usa LLM nem OpenAlex. `OPENAI_API_KEY` e `DATABASE_URL` são tratadas como segredos, pois a URL do banco contém credenciais. `CORS_ORIGINS` tem valor padrão `['*']` para preservar o comportamento atual do stub, mas pode receber uma lista explícita de origens.

O ponto de entrada ativo ainda é `verificador/backend/main.py`. A validação inicial deve ocorrer nele; quando a aplicação migrar para `src/main.py`, o mesmo objeto de configuração deverá ser reutilizado, sem criar uma segunda fonte de verdade.

## 3. Critérios de aceite

1. `src/core/config/settings.py` expõe uma classe `Settings` com `APP_DEBUG`, `OPENAI_API_KEY`, `DATABASE_URL`, `OPENALEX_MAILTO` e `CORS_ORIGINS`, todas documentadas em `.env.example`.
2. `Settings` lê valores do arquivo `.env` do backend e aceita sobrescrita por variáveis de ambiente, sem depender do diretório de onde o processo foi iniciado.
3. `APP_DEBUG` é interpretada como booleano; na ausência de valor, assume `false`.
4. `DATABASE_URL` ausente, vazia ou composta apenas por espaços causa erro de validação durante a inicialização da aplicação, antes de qualquer requisição.
5. `OPENAI_API_KEY` ausente ou vazia não impede a inicialização do stub atual; quando fornecida, seu valor não aparece no `repr` de `Settings`, em logs da aplicação nem no texto de erros de validação. O mesmo sigilo vale para o valor de `DATABASE_URL`.
6. `OPENALEX_MAILTO` ausente ou vazia não impede a inicialização do stub atual; quando fornecida, fica disponível em `Settings`.
7. `get_settings()` retorna a mesma instância em chamadas sucessivas e oferece limpeza do cache para que testes consigam alterar a configuração entre casos.
8. Um teste unitário cobre configuração válida com os cinco campos, outro cobre `DATABASE_URL` ausente/vazia e outro demonstra sobrescrita isolada sem depender de um `.env` real.
9. `CORS_ORIGINS` ausente preserva a política atual de permitir qualquer origem; quando recebe uma lista de origens, o middleware CORS usa exatamente essa lista.
10. A aplicação usa a instância centralizada na inicialização para configurar `APP_DEBUG` e CORS; não cria um segundo objeto de configuração com os mesmos campos.

## 4. Fora de escopo

- Conectar ao banco ou validar se `DATABASE_URL` aponta para um servidor acessível.
- Chamar OpenAI ou OpenAlex, criar agentes ou alterar o veredicto fixo do stub.
- Tornar `OPENAI_API_KEY` ou `OPENALEX_MAILTO` obrigatórias antes de suas integrações serem implementadas.
- Introduzir novos segredos ou publicá-los em documentação.
- Alterar o contrato HTTP de `/verificar` ou a extensão.
- Migrar toda a aplicação para `src/main.py` (trabalho separado da task #7).
- Introduzir `APP_PORT`: a porta é configurada no comando ou ambiente do Uvicorn, não no objeto de configuração da aplicação.
- Definir nova política de segurança CORS; esta entrega somente torna configurável a lista de origens e preserva o padrão atual.

## 5. Comportamento de IA

Não se aplica. Esta feature não faz chamadas a LLM; seu comportamento é determinístico e coberto por testes comuns.

## 6. Perguntas em aberto

Nenhuma para o escopo desta spec.

## 7. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-18 | Criação da spec 006 a partir da task #6 |
| 2026-09-18 | Inclui `CORS_ORIGINS`, mantém a porta no Uvicorn e remove decisões sobre features futuras |
| 2026-09-19 | Implementa a configuração, o uso no stub e os testes; revisão formal pendente |
