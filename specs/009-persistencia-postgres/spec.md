# 009 — Camada de persistência do Verificador

| Campo | Valor |
| :--- | :--- |
| **Status** | em revisão |
| **Autor** | Equipe Arial 12 |
| **Branch** | `feature/009-persistencia-postgres` |
| **Depende de** | `006` — configuração centralizada |
| **Origem** | [Task #9](https://github.com/unb-Sistemas-de-Machine-learning/challenge_1_arial_12/issues/9) |

---

## 1. Objetivo

O sistema passa a guardar o que já foi verificado e o que o usuário achou do
resultado, para que uma verificação repetida seja respondida sem refazer o
trabalho e para que a taxa de aceitação possa ser medida.

## 2. Contexto

O contêiner **Postgres Database** da [arquitetura](../../docs/pages/arquitetura.md)
sobe junto com a aplicação desde a spec 007, e a `DATABASE_URL` é validada na
inicialização desde a 006 — mas nada no código abria conexão com ele.

Isso travava dois contêineres da esteira: o **Cache Validator**, que não tinha
onde consultar buscas recentes, e o registro de feedback que o **API Gateway**
faz. Esta spec entrega a camada que os dois vão consumir, sem implementar
nenhum dos dois.

## 3. Critérios de aceite

1. Existem duas tabelas: uma guarda cada verificação feita — o trecho avaliado,
   o estado do veredito, a resposta completa e o momento com fuso horário — e
   outra guarda cada avaliação do usuário, apontando para a verificação que
   avaliou.
2. Verificações equivalentes são reconhecidas por uma chave derivada do trecho
   selecionado e normalizada, de forma que o mesmo texto escrito com espaçamento
   ou caixa diferentes produza a mesma chave. A chave é indexada e **não** é
   única.
3. A chave **não** deriva de texto produzido por agente de IA: saída de LLM não
   se repete entre execuções, e uma chave baseada nela nunca encontraria nada.
4. Várias avaliações podem existir sobre a mesma verificação, inclusive
   opostas, e nenhuma sobrescreve a outra.
5. A sessão de banco é fornecida por dependência da aplicação e encerrada ao fim
   da requisição, inclusive quando a rota levanta exceção.
6. Aplicar as migrações sobre um banco vazio cria o schema completo, e desfazê-
   las devolve o banco ao estado vazio. O ciclo funciona mais de uma vez.
7. Uma alteração nos modelos sem a migração correspondente reprova nos testes.
8. As operações expostas usam o vocabulário do domínio — registrar uma
   verificação, procurar por chave, registrar uma avaliação — e não devolvem
   objetos internos da ferramenta de persistência.
9. Os testes de integração rodam contra um Postgres real e são isolados por
   transação revertida: o que um caso grava não existe para o seguinte.

## 4. Fora de escopo

- **Qualquer rota nova.** Esta spec não expõe endpoint de feedback nem altera o
  contrato com a extensão; isso é a task #21. Consequência aceita: a camada
  existe e está testada, mas nenhuma rota de produção a exercita ainda.
- **A lógica do cache.** Decidir por quanto tempo um registro continua válido é
  de outra entrega. Aqui existe apenas a capacidade de encontrar um registro
  equivalente.
- **A esteira de agentes.** Nada de Triador, OpenAlex, BERTopic ou Juiz.
- **Painel ou consulta da taxa de aceitação.** O dado passa a ser gravado;
  apresentá-lo é outra demanda.
- **Healthcheck consultando o banco.** Definido na spec 007 como verificação que
  não toca dependência externa, e continua assim.

## 5. Comportamento de IA

Não se aplica. Esta feature não invoca LLM e é testável de forma determinística.

## 6. Perguntas em aberto

- [x] **A chave de busca é única?** Não. Resolvido em 2026-09-22: com
      unicidade, uma verificação refeita depois de o cache vencer só poderia
      sobrescrever a linha existente, e as avaliações já dadas passariam a
      apontar para uma resposta que ninguém viu — a taxa de aceitação
      continuaria sendo calculada, e estaria errada sem nenhum sinal.
- [ ] **O nome da tabela de histórico diverge da task #9.** A task pede
      `historico_busca`; esta entrega usa `veredito`, porque a linha guarda o
      resultado da análise e não apenas o registro da busca. Mesma estrutura,
      nome diferente. **A confirmar com o autor da task.**

## 7. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-22 | Implementação da task #9 |
| 2026-09-23 | Criação da spec. Escrita **depois** da implementação, contrariando o passo 5 do processo — registrado aqui em vez de omitido, para o histórico refletir o que aconteceu |
