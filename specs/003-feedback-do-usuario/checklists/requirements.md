# Checklist de qualidade da spec: 003 - Feedback do usuário

**Objetivo**: validar a completude da especificação antes de passar ao `plan.md`
**Criado em**: 2026-09-16
**Spec**: [spec.md](../spec.md)

## Qualidade do conteúdo

- [x] Sem detalhe de implementação (biblioteca, framework, SQL)
- [x] Focada em valor para o usuário e na métrica do produto
- [x] Legível por quem não implementa
- [x] Todas as seções obrigatórias do `specs/_template/` preenchidas

## Completude dos requisitos

- [x] Nenhum `[NEEDS CLARIFICATION]` restante — dúvidas na seção 8
- [x] Critérios de aceite testáveis e não ambíguos
- [x] Critérios de sucesso mensuráveis e independentes de tecnologia
- [x] Estados de erro e vazio cobertos (critérios 3, 6, 10)
- [x] Acessibilidade tratada (critérios 7 e SC-05)
- [x] Escopo delimitado (seção 4)
- [x] Premissas registradas (seção 7)

## Conformidade com a constituição

- [x] **I — Spec antes do código**: a extensão ainda não tem nada disto implementado
- [x] **II — Contrato primeiro**: `/feedback` e o schema da tabela definidos antes do consumidor
- [x] **III — Determinístico se testa**: seção 5 declara ausência de LLM e, portanto, de eval set
- [x] **IV — Latência e custo**: SC-03 trata do retorno imediato; a feature não gasta token
- [x] **V — Rastreabilidade**: número, slug e branch declarados; dependência da 002 explícita

## Pontos de atenção levantados na validação

- **Critério 13 é o ponto frágil do desenho.** Se alguém gerar `id_requisicao` como hash da
  alegação — o que é tentador, porque serve de chave de cache ao mesmo tempo — as duas
  ilhas de dados voltam a se ligar e o critério 25 da 002 cai por terra sem ninguém
  perceber. Vale um teste explícito de que ids de duas verificações da **mesma** alegação
  são diferentes.
- **Critério 14 refina o critério 28 da 002**, que falava em gravar métricas junto do voto.
  Aqui a linha nasce com a verificação e o voto a completa depois. É compatível, mas a 002
  deve ser ajustada por emenda quando esta spec for aprovada.
- **Critério 2 amplia o escopo do voto** para `nao_verificavel`. Isso é de propósito: é o
  único sinal de que o portão do Triador está barrando coisa demais — o "erro caro"
  apontado no eval do Triador na 002.
- A pergunta em aberto nº 1 muda o que o comando do critério 17 imprime. Resolver antes do
  `plan.md`, não durante.
