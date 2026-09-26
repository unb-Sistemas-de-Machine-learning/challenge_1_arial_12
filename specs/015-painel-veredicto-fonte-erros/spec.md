# 015 — Painel de veredicto com fonte clicável e estados de erro

| Campo | Valor |
| :--- | :--- |
| **Status** | em revisão |
| **Autor** | Equipe Arial 12 |
| **Branch** | `feature/015-painel-veredicto-fonte-erros` |
| **Depende de** | #10 (contrato de `/verificar`), #14 (URL da API no build) |
| **Origem** | [Issue #15](https://github.com/unb-Sistemas-de-Machine-learning/challenge_1_arial_12/issues/15) |

## 1. Objetivo

O leitor vê o veredito e pode abrir a publicação citada; quando a verificação falha, entende o motivo e pode repetir a tentativa sem selecionar o trecho novamente.

## 2. Contexto

A extensão já envia o trecho ao gateway e mostra o veredito mock, mas o DOI não é clicável, a retratação se mistura à metainformação e erros podem aparecer sem uma ação útil. A identidade visual está em `docs/pages/style_guidelines.md` e `docs/assets/style_guidelines/colors.png`. A issue cita uma spec `001`, inexistente neste repositório; a seção de interface fica registrada aqui, sem criar uma spec retroativa.

## 3. Interface e critérios de aceite

1. Um estudo com DOI apresenta link `https://doi.org/<doi>` em nova aba, com `target="_blank"` e `rel="noopener noreferrer"`. Caracteres especiais do DOI são codificados como parte do caminho, nunca interpretados como protocolo, query ou fragmento.
2. `estudo: null` com `estado: "nada_encontrado"` não cria bloco de estudo nem texto `null`.
3. `retratado: true` mostra aviso próprio com texto “Estudo retratado”, visualmente separado do badge do veredito.
4. Os badges são rotulados e usam a paleta da identidade visual: `sustenta`/Embasado `#27AE60`, `exagera` `#F89A3C`, `nada_encontrado` `#F9D159`; erro `#EB5757`. A cor nunca é a única indicação do estado.
5. Os códigos públicos do backend são traduzidos em português num módulo próprio; texto cru da API, endereço local, porta e stack não aparecem no painel. Código desconhecido recebe mensagem genérica.
6. Falha de rede mostra “Tentar novamente”. A ação reutiliza exatamente o trecho e a URL da tentativa anterior, sem depender da seleção atual.
7. Fechar o painel durante uma verificação solicita o cancelamento da chamada ao backend e invalida a resposta pendente; esta não reabre o painel. Iniciar outra verificação também cancela/invalida a anterior.
8. O painel mantém uma opção de fechamento acessível por nome, e o estado de carregamento informa o andamento em texto.
9. Testes automatizados cobrem renderização de DOI, estudo ausente, retratação, três estados, mensagens de erro e controle de requisições concorrentes/canceladas.
10. O roteiro manual do README é executado em Chrome e Firefox, com evidências visuais dos três estados e do erro antes de concluir o PR.

## 4. Fora de escopo

- Mudar o contrato ou o veredito mock do backend. O mock só retorna `exagera`; os outros estados podem ser exercitados em testes ou com respostas simuladas.
- Implementar busca real ou validação editorial de estudos.
- Alterar a configuração da URL da API definida na #14.

## 5. Comportamento de IA

Não se aplica. O painel e o mapeamento são determinísticos.

## 6. Validação realizada e pendências

- O fluxo principal foi aprovado manualmente no Chrome: `exagera`, link DOI abrindo em nova aba, mensagem de erro de rede e retry do mesmo trecho. Há evidências visuais do veredito e do erro.
- Um estado de veredito foi usado como evidência visual do painel. `sustenta`, `nada_encontrado`, estudo ausente e retratação foram simulados pelos testes automatizados; isso não equivale a capturas desses estados no navegador.
- O Firefox não foi testado manualmente após a aprovação no Chrome, pois não está disponível neste ambiente. O build Firefox passou, mas build não comprova comportamento visual.
- O critério 10 da issue ainda pede roteiro nos dois navegadores e capturas dos três estados. Essa diferença deve ficar explícita no PR e depende de aceitação dos revisores; não está marcada como cumprida nesta spec. O cancelamento também tem teste automatizado, sem evidência visual manual registrada.

## 7. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-25 | Spec da issue #15; interface documentada aqui porque `001` não existe no repositório |
| 2026-09-25 | Registra aprovação do fluxo principal no Chrome e evidências de `exagera`/erro; mantém explícitas as validações visuais não realizadas |
