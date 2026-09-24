# 010 - Contrato de verificação entre extensão e backend

| Campo          | Valor                                                              |
| :------------- | :----------------------------------------------------------------- |
| **Status**     | em revisão                                                         |
| **Autor**      | Bruno Ricardo de Menezes                                           |
| **Branch**     | `feature/010-rota-verificar-health`                                 |
| **Depende de** | `#7` — integrada nesta branch                                       |

---

## 1. Objetivo

Garantir que a extensão e o backend utilizem um contrato único, validado e documentado para o envio de alegações e recebimento de veredictos, sem quebrar a compatibilidade com a extensão já existente.

Disponibilizar esse contrato por meio do OpenAPI para que a evolução da extensão e da aquisição de evidências possa ocorrer de forma independente contra a mesma definição.

## 2. Contexto

Esta feature pertence à interface entre a **extensão do navegador** e o **backend do verificador**, dentro da esteira descrita em [Arquitetura](../../docs/pages/arquitetura.md).

Na Fase 01, o contrato de comunicação existia em duas representações independentes:

* no backend legado, em `verificador/backend/main.py`, onde `Pedido` representa parcialmente a entrada e o veredicto é retornado como um dicionário sem validação formal;
* na extensão, em `verificador/extensao/tipos.ts`, onde `Estado`, `Estudo` e `Veredito` representam o formato esperado pelo cliente.

Como essas definições não são verificadas entre si, o backend pode alterar campos, tipos ou valores permitidos sem que a divergência seja detectada antes da execução da extensão.

Esta spec formaliza esse contrato no backend por meio de modelos validados e o publica no OpenAPI da aplicação.

As rotas `POST /verificar` e `GET /health` passam a fazer parte da aplicação em `src/main.py`. A rota `/health` foi padronizada na task **#7**; esta feature migra `/verificar` para o gateway e integra a fábrica de aplicação daquela task.

Nesta etapa, `/verificar` continua retornando o mesmo veredicto fixo utilizado pelo stub. A substituição do mock por aquisição e análise real de evidências pertence a etapas posteriores.

A compatibilidade retroativa é obrigatória: uma extensão já instalada deve continuar consumindo `/verificar` sem recompilação e sem alteração do formato JSON recebido.

## 3. Critérios de aceite

1. `POST /verificar` recebe uma requisição contendo `trecho` e, opcionalmente, `url`, e responde com status HTTP `200` quando os dados são válidos.

2. A resposta bem-sucedida de `POST /verificar` valida integralmente contra o modelo `Veredito`.

3. O campo `estado` aceita exclusivamente os valores `sustenta`, `exagera` e `nada_encontrado`.

4. A construção de um `Veredito` com qualquer valor de `estado` diferente dos valores permitidos falha antes da serialização da resposta.

5. O campo `url` é opcional e aceita, quando informado, URLs com esquema `file://`, preservando o funcionamento da `pagina-teste.html` utilizada no roteiro local.

6. O campo `estudo` de `Veredito` aceita `null`.

7. Quando `estudo` não é `null`, os campos `titulo`, `ano`, `doi` e `retratado` estão presentes; `ano` e `doi` aceitam `null`, conforme o contrato da extensão.

8. `GET /health` responde com HTTP `200` e corpo:

```json
{
  "ok": true
}
```

9. `GET /health` funciona sem estabelecer conexão com o banco de dados, inclusive quando `DATABASE_URL` aponta para um host inacessível.

10. O JSON retornado por `POST /verificar` é idêntico, campo a campo e na mesma estrutura de aninhamento, ao payload produzido pelo stub da Fase 01 e registrado como fixture antes da remoção do stub.

11. Os campos expostos pelos modelos de contrato do backend permanecem equivalentes aos campos declarados em `verificador/extensao/tipos.ts`.

12. Os valores aceitos pelo enum `Estado` no backend permanecem equivalentes aos valores declarados pelo tipo correspondente em `verificador/extensao/tipos.ts`.

13. Existe um teste automatizado que falha quando houver divergência de campos entre o contrato Pydantic do backend e `verificador/extensao/tipos.ts`.

14. Existe um teste automatizado que falha quando o conjunto de valores de `Estado` divergir entre o backend e `verificador/extensao/tipos.ts`.

15. `POST /verificar` e `GET /health` aparecem na documentação disponível em `/docs`.

16. A documentação de `POST /verificar` contém exemplo de requisição e exemplo da resposta esperada.

17. `/openapi.json` expõe os tipos, campos obrigatórios, enum de `Estado` e as regras de validação definidas para o contrato.

18. Nenhuma rota de negócio permanece em `verificador/backend/main.py` após a migração.

19. O arquivo `verificador/backend/main.py` é removido após a preservação do payload legado utilizado como fixture.

20. O `docker-compose.yml` não mantém volume destinado ao antigo `verificador/backend/main.py`.

21. O roteiro manual descrito em `verificador/README.md` é executado com uma extensão previamente instalada e sem recompilação.

22. Durante o roteiro manual, a extensão consegue enviar uma verificação à nova implementação de `POST /verificar` e interpretar sua resposta sem alteração no código cliente.

23. A resposta exibida para a extensão preserva o comportamento observado na Fase 01.

## 4. Fora de escopo

* Implementar busca real de evidências acadêmicas.
* Integrar `/verificar` à OpenAlex ou a qualquer outro provedor de dados científicos.
* Implementar o Agente Triador, Agente Pesquisador, Agente Juiz ou qualquer outra etapa baseada em IA.
* Utilizar LLM para produzir ou classificar o veredicto.
* Alterar o conteúdo ou a regra do veredicto fixo existente na Fase 01.
* Alterar o contrato TypeScript da extensão para acomodar mudanças no backend.
* Recompilar a extensão como requisito para a migração.
* Alterar a interface visual ou o fluxo de interação da extensão.
* Implementar persistência do resultado da verificação.
* Tornar o banco de dados requisito para o funcionamento de `GET /health`.
* Implementar cache de consultas ou resultados.
* Implementar rate limiting.
* Definir políticas de CORS além das já existentes.
* Implementar autenticação ou autorização nas rotas.
* Padronizar todos os erros da aplicação além daqueles resultantes diretamente da validação deste contrato.
* Definir nesta spec a implementação interna dos modelos, routers ou mecanismo utilizado pelo teste de paridade com TypeScript.

## 5. Comportamento de IA

Não se aplica.

Esta feature não utiliza LLM nem possui comportamento probabilístico. Todas as entradas, validações, estruturas de resposta e critérios de compatibilidade definidos nesta spec são determinísticos e devem ser verificáveis por testes automatizados ou pelo roteiro manual de compatibilidade.

## 6. Perguntas em aberto

* [ ] **Tamanho mínimo e máximo de `trecho`: indefinidos nesta etapa.** <!-- TODO: definir os limites em revisão futura da spec e acrescentar os respectivos critérios de aceite e testes. -->
* [ ] **Tamanho máximo da justificativa do veredicto: indefinido nesta etapa.** <!-- TODO: definir o limite em revisão futura da spec e acrescentar o respectivo critério de aceite e teste. -->

## 7. Histórico

| Data       | Mudança |
| :--------- | :------ |
| 2026-09-18 | Criação da spec |
| 2026-09-18 | Define `/health` como rota de saúde e deixa os limites de tamanho para revisão futura |
| 2026-09-18 | Alinha a obrigatoriedade de `ano` e `doi` ao contrato TypeScript da extensão |
| 2026-09-18 | Implementação automatizada concluída; mantém revisão da spec, integração com #7 e teste manual pendentes |
| 2026-09-18 | Renumera a entrega para feat 10 (spec 010) |
| 2026-09-19 | Integra a fábrica e o Compose da task #7; preserva `/verificar` no gateway e remove o stub legado |
| 2026-09-23 | Confirma o critério 9 com URL bem formada para host inacessível; 62 testes passaram com PostgreSQL isolado e a extensão passou na checagem de tipos. Roteiro manual pendente. |
