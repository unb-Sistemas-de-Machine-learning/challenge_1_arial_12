# 008 — Verificação automática de lint e testes em cada PR

| Campo | Valor |
| :--- | :--- |
| **Status** | implementada |
| **Autor** | Equipe Arial 12 |
| **Branch** | `feature/008-ci-ruff-pytest` |
| **Depende de** | `007` — inicialização pelo Docker Compose |
| **Origem** | [Task #8](https://github.com/unb-Sistemas-de-Machine-learning/challenge_1_arial_12/issues/8) |

---

## 1. Objetivo

Quem abre um PR descobre que quebrou algo antes de pedir revisão, e quem revisa
vê o resultado de lint, testes e checagem de tipos sem precisar clonar a branch
e rodar os comandos na mão.

## 2. Contexto

A [Política de Branches e Commits](../../docs/pages/politicas_repositorio.md)
exige revisão e aprovação em todo PR, mas nada garantia que essa aprovação fosse
dada com a suíte verde — não havia automação nenhuma no repositório.

A spec 007 deixou a aplicação subindo por Compose e a suíte estável, o que
tornou possível automatizar a verificação. Esta entrega não toca em nenhum
contêiner da [arquitetura](../../docs/pages/arquitetura.md): é infraestrutura de
desenvolvimento.

## 3. Critérios de aceite

1. Abrir ou atualizar um PR para a `main` dispara a verificação sem ninguém
   pedir.
2. A verificação do backend reprova quando há erro de lint, quando a formatação
   diverge do padrão, ou quando um teste falha — cada um isoladamente.
3. A verificação da extensão reprova quando a checagem de tipos acusa erro.
4. As duas verificações rodam ao mesmo tempo e reaproveitam dependências entre
   execuções.
5. Nenhuma verificação acessa a rede em teste unitário nem exige chave real de
   provedor externo.
6. A configuração de lint e de testes do backend fica declarada em arquivo
   versionado, de modo que a mesma regra valha na automação e na máquina de
   quem desenvolve.
7. Teste assíncrono sem marcação explícita passa a ser erro, e não silêncio —
   sem isso ele é coletado, ignorado, e a suíte fica verde sem ter rodado.
8. Existe prova registrada de que a verificação reprova de fato: uma execução
   vermelha provocada por um teste quebrado de propósito, seguida da execução
   verde após o conserto.

## 4. Fora de escopo

- **Banco de dados na verificação.** Entrou depois, pela spec 009, que
  acrescentou o serviço ao trabalho já pronto.
- **Meta mínima de cobertura.** Sem histórico, qualquer número seria arbitrário.
- **Build da imagem e subida dos contêineres na verificação.** O que a imagem
  quebra aparece ao subir o ambiente, não em lint e teste unitário.
- **Varredura de segurança e de dependências.** Fica para ciclo futuro.

## 5. Comportamento de IA

Não se aplica. Esta feature não invoca LLM.

## 6. Perguntas em aberto

- [x] **O gatilho cobre `develop` e `main`, como pede a task #8?** Não. Apenas
      a `main`. Verificado em 2026-09-22: **a branch `develop` não existe no
      repositório remoto**, e os PRs #22 e #23 foram mesclados direto na `main`.
      Listar uma branch inexistente funcionaria sem erro, mas o arquivo passaria
      a descrever um fluxo que não é o praticado. Quando a equipe criar a
      `develop`, é preciso acrescentá-la ao gatilho **e** configurar a proteção
      nela.
- [ ] **A `develop` deve existir?** A política de branches a descreve como
      branch de integração, mas ela nunca foi criada e o time trabalha direto
      contra a `main`. Ou a branch é criada, ou a política é corrigida para
      refletir o fluxo real. **Decisão da equipe** — não desta spec.
- [ ] **As verificações estão marcadas como obrigatórias na proteção da
      `main`?** A regra de proteção existe e exige uma revisão aprovada, mas
      falta confirmar se os dois checks foram acrescentados como obrigatórios.
      Enquanto não forem, um PR com verificação vermelha ainda pode ser
      mesclado: o vermelho informa, mas não impede.

## 7. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-22 | Implementação da task #8 e merge pelo PR #24 |
| 2026-09-22 | Gatilho restrito à `main` ao descobrir que a `develop` não existe |
| 2026-09-23 | Criação da spec, **depois** da implementação e do merge. Registrado aqui em vez de omitido |
