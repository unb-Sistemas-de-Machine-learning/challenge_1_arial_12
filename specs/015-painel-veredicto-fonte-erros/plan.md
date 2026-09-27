# Plano — 015 Painel de veredicto

## Abordagem

Separar as mensagens de erro e a renderização do painel em módulos testáveis. O content script coordena carregamento, retry e fechamento usando um identificador por tentativa. O background associa esse ID a um `AbortController`, permitindo cancelar o `fetch`; o content script ignora qualquer resposta tardia mesmo se o cancelamento não chegar a tempo.

## Arquivos

| Arquivo | Mudança |
| :--- | :--- |
| `verificador/extensao/mensagens-erro.ts` | mapa fechado código → mensagem amigável |
| `verificador/extensao/painel.ts` | HTML seguro para estados, fonte DOI e retratação |
| `verificador/extensao/entrypoints/content.ts` | interação, retry, cancelamento e CSS da identidade visual |
| `verificador/extensao/entrypoints/background.ts` | `AbortController` por tentativa e resposta com código estável |
| `verificador/extensao/requisicoes.ts` | cliente testável que executa e aborta o `fetch` |
| `verificador/extensao/tipos.ts` | mensagens de verificar/cancelar e erro discriminado |
| `verificador/extensao/tests/` | testes unitários da apresentação e do controle de tentativas |
| `.github/workflows/ci.yml` | executa os testes da extensão após a checagem de tipos |
| `verificador/README.md` | roteiro manual atualizado para a UI |

## Decisões

- DOI codificado como caminho e texto escapado antes de interpolar em HTML.
- Cor de badge com texto escuro para legibilidade, mantendo rótulo textual.
- Retry apenas na falha de rede; erros HTTP têm mensagem orientada ao usuário, sem repetir automaticamente.
- ID de tentativa exclusivo separa resposta antiga de nova; o fechamento invalida o ID mesmo se o background já tiver respondido.
- O mock atual não cobre os três estados no navegador: os testes de renderização cobrem todos; capturas reais exigem respostas simuladas ou integração posterior.

## Verificação

`npm run compile`, `npm test` (transpila os módulos TypeScript para `.test-dist` e roda os testes em Node 20+), build Chrome/Firefox e roteiro manual em ambos. Evidências manuais pendentes devem ser descritas sem afirmar que foram executadas.
