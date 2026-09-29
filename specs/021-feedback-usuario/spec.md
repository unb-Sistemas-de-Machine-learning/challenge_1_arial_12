# 021 - Feedback do Usuário

| Campo | Valor |
| :--- | :--- |
| **Status** | aprovada |
| **Autor** | Antigravity |
| **Branch** | `feature/021-feedback-usuario` |
| **Depende de** | `015`, `009` |

---

## 1. Objetivo

Permitir que o usuário avalie com um clique se o veredicto foi útil ou não. A equipe usará esse feedback para entender quando a ferramenta erra e melhorar a assertividade dos agentes.

## 2. Contexto

Esta feature adiciona controles na interface da extensão (Painel de Veredicto) e uma nova rota no backend para registrar a avaliação. Depende da interface visual estabelecida na spec `015` e da camada de persistência implementada na spec `009`.

## 3. Critérios de aceite

1. O painel exibe dois controles de avaliação (positivo e negativo) assim que o veredicto é renderizado.
2. Uma requisição `POST /feedback` grava a avaliação, o identificador do veredicto avaliado e a data/hora com timezone no banco de dados.
3. A gravação é assíncrona: a resposta ao usuário não espera a escrita no banco de dados, e uma eventual falha no banco de dados não mostra erro na interface do usuário.
4. Após avaliar, o painel confirma visualmente o recebimento e impede o reenvio do mesmo feedback.
5. Nenhum dado pessoal é enviado: sem identificador de usuário, sem histórico de navegação. A URL da página não será enviada (resolvido na seção de perguntas em aberto).
6. O `manifest.json` da extensão continua declarando `data_collection_permissions: { required: ["none"] }`. Nenhuma nova permissão é solicitada.
7. A rota `POST /feedback` possui rate limiting para não virar um vetor de inflação de métricas.
8. Existem testes automatizados cobrindo a gravação bem-sucedida, tratamento de payload inválido e comportamento em caso de banco de dados indisponível.

## 4. Fora de escopo

- Painel de administração para visualização dos feedbacks (será tratado em spec futura).
- Vinculação do feedback a usuários logados (a extensão não tem login).
- Coleta de comentários em texto livre do usuário (apenas botão útil / não útil).

## 5. Perguntas em aberto

- [x] O que exatamente é enviado no payload?
  **Resposta**: Apenas a avaliação (ex: `util: true` ou `false`), o `veredicto_id` (identificador único gerado na verificação), e a `data_hora` em UTC. A URL não é necessária, pois a equipe apenas avalia a performance dos agentes e já tem os metadados associados ao `veredicto_id` no backend. Enviar a URL violaria o princípio de `data_collection_permissions: ["none"]` sem uma justificativa técnica forte, e não faremos isso.

## 6. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-28 | Criação da spec |
