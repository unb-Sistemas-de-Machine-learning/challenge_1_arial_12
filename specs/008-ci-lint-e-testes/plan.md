# Plano — 008 Verificação automática de lint e testes em cada PR

> Plano técnico da task #8. A spec registra o comportamento; este arquivo detalha como implementá-lo.

## 1. Abordagem

Um workflow do GitHub Actions com dois jobs independentes — `backend` e `extensao` — disparados por PR para a `main`. Cada job sobe numa máquina própria, o que já garante o paralelismo sem configuração extra, e fixa seu diretório de trabalho, porque os dois projetos vivem em subpastas e nenhum comando funciona a partir da raiz.

O backend ganha um `pyproject.toml` com a configuração de `ruff` e `pytest`, para que a mesma regra valha na automação e na máquina de quem desenvolve. O código existente é formatado num commit isolado, antes do workflow existir — sem isso a verificação nasceria vermelha por causa de código entregue nas specs 006 e 007.

## 2. Arquivos tocados

| Arquivo | O que muda |
| :--- | :--- |
| `.github/workflows/ci.yml` | Gatilho, permissão de leitura, cancelamento de execuções antigas e os dois jobs |
| `verificador/backend/pyproject.toml` | Limite de linha e versão de destino do `ruff`; caminho dos testes e modo estrito do `pytest-asyncio` |
| `verificador/backend/src/core/config/settings.py` | Apenas reformatação |
| `verificador/backend/src/tests/unit/test_settings.py` | Apenas reformatação |
| `verificador/backend/src/tests/integration/test_startup_settings.py` | Apenas reformatação |

## 3. Contratos

```yaml
on:
  pull_request:
    branches: [main]

jobs:
  backend:    # ruff check . | ruff format --check . | pytest
  extensao:   # npm ci | npm run compile
```

Os nomes dos jobs são contrato: a proteção de branch guarda o nome em texto ao marcar a verificação como obrigatória, e o GitHub a exibe como `CI / backend` e `CI / extensao`. Renomear um job desliga a obrigatoriedade em silêncio.

## 4. Decisões técnicas

| Decisão | Alternativa descartada | Por quê |
| :--- | :--- | :--- |
| Gatilho só na `main` | `develop` e `main`, como pede a task | A `develop` não existe no repositório; o arquivo descreveria um fluxo que não é o praticado |
| Python 3.12 na automação | Versão mais recente disponível | É a versão da imagem Docker; testar em outra esconde justamente o erro que importa |
| Dois jobs separados | Um job com etapas sequenciais | Em job único, a falha do backend impede a extensão de rodar e o autor descobre um problema por vez |
| Manter o limite de linha padrão | Aumentar para evitar reformatar | Mudar o limite é decisão de estilo permanente que a equipe herdaria sem discutir |
| Reformatação em commit isolado | Misturada ao resto do PR | O revisor não distinguiria mudança real de quebra de linha |
| Modo estrito do `pytest-asyncio` | Modo automático | Teste assíncrono sem marcação é coletado e ignorado em silêncio; a suíte fica verde sem ter rodado |
| Não transformar aviso em erro | Reprovar em qualquer aviso | Uma dependência de terceiro emite aviso de depreciação fora do nosso controle |
| `pyproject.toml` no backend | Na raiz do repositório | Na raiz sugeriria que o repositório inteiro é um pacote Python |

## 5. Como testar

- **Local:** rodar os quatro comandos do workflow antes de publicar, para separar erro de automação de erro de código.
- **Sintaxe:** carregar o arquivo do workflow com um leitor de YAML antes do push. Erro de indentação não deixa o check vermelho — deixa o PR **sem check**, falha que se parece com sucesso.
- **Prova da reprovação:** quebrar uma asserção de propósito, esperar a execução vermelha terminar, registrar o link, e só então corrigir. O workflow cancela execuções antigas quando chega commit novo; empurrar a correção cedo demais destrói a prova.
- **Eval:** não se aplica.

## 6. Riscos

- A reformatação toca arquivos entregues pelas specs 006 e 007; o commit isolado e um aviso na descrição do PR evitam o susto do revisor.
- A configuração de tipos da extensão é gerada pelo `postinstall` e está no `.gitignore`; verificado que `npm ci` a gera, e que sem esse passo a checagem de tipos não teria o que estender.
- A obrigatoriedade das verificações depende de quem tem permissão de administrador; enquanto não for ligada, o vermelho informa mas não impede o merge.
