# Política de Branches e Commits

Este documento define os padrões de ramificação (branches) e de mensagens de commit para o repositório do projeto, visando garantir colaboração segura, histórico limpo e rastreabilidade das entregas.

## 1. Política de Branches

### Estrutura e Convenção de Nomes

Os nomes das branches devem ser curtos, em minúsculas e separados por hífen.

*   `main`: Código em produção/homologação. Protegida, apenas recebe conteúdo testado e aprovado.
*   `develop`: Branch de integração contínua das mudanças do ciclo atual.
*   `feature/*`: Novas funcionalidades ou melhorias. (Ex: `feature/autenticacao-usuario`)
*   `bugfix/*` ou `fix/*`: Correções de bugs identificados em desenvolvimento. (Ex: `fix/link-quebrado-menu`)
*   `hotfix/*`: Correções urgentes em produção (`main`). (Ex: `hotfix/correcao-pagamento`)
*   `docs/*`: Criação ou alteração de documentação. (Ex: `docs/diagramas-arquitetura`)
*   `chore/*`: Tarefas técnicas, configuração ou build. (Ex: `chore/atualiza-dependencias`)
*   `release/*`: Preparação final de versão para publicação. (Ex: `release/v1.0.0`)

### Fluxo de Trabalho e Regras de Proteção

1.  **Sem pushes diretos:** Ninguém faz commit direto nas branches `main` ou `develop`.
2.  **Criação:** Crie uma branch a partir da `develop` (ex: `feature/nova-tela`) para iniciar o trabalho.
3.  **Commits:** Faça os commits seguindo a Política de Commits estabelecida abaixo.
4.  **Pull Request (PR):** Abra um PR direcionado à `develop` com uma descrição clara e objetiva do que foi feito.
5.  **Revisão:** Todo PR exige revisão e aprovação de pelo menos um integrante da equipe.
6.  **Merge:** Priorize a estratégia **Squash and Merge** para manter o histórico da branch principal limpo, contendo apenas um commit por entrega.
7.  **Limpeza:** Após o merge, exclua a branch de origem para reduzir o ruído no repositório.

---

## 2. Política de Commits

Adotamos o padrão **Conventional Commits** com mensagens escritas em português.

### Padrão da Mensagem

```text
tipo(escopo-opcional): descrição
``` 

### Regras da Mensagem

1. O título deve ter no máximo 72 caracteres.
2. A descrição deve ser objetiva e específica.
3. A descrição deve ser escrita em tom imperativo.
4. A descrição não deve terminar com ponto final.
5. O escopo é opcional, mas recomendado quando agregar clareza.
6. Commits genéricos como `update`, `ajustes` e `mudanças` não são permitidos.

### Tipos Permitidos

| Tipo       | Quando usar | Exemplo |
| ---------- | ----------- | ------- |
| `feat`     | Nova funcionalidade ou conteúdo novo relevante | `feat(projeto): adiciona seção de riscos na EAP` |
| `fix`      | Correção de erro, inconsistência ou comportamento incorreto | `fix(docs): corrige sumário da lean inception` |
| `docs`     | Alteração apenas de documentação | `docs: atualiza política de branches` |
| `style`    | Ajustes de formatação sem mudança de conteúdo | `style(roadmap): padroniza cabeçalhos de seção` |
| `refactor` | Reorganização estrutural sem alterar resultado final | `refactor(produto): reorganiza tópicos do backlog` |
| `test`     | Inclusão ou ajuste de testes e validações | `test: adiciona checklist de revisão dos documentos` |
| `chore`    | Tarefas de manutenção, configuração e rotina | `chore: atualiza dependências do mkdocs` |

### Corpo e Rodapé do Commit

Use corpo de commit quando a mudança não puder ser explicada com clareza em uma
única linha, especialmente quando envolver:

Formato recomendado:

```text
feat(api): adiciona rota de exportação de relatórios

Contexto: A funcionalidade permite baixar os dados analíticos.
Impacto: Requer atualização dos endpoints no Swagger.

Refs: #123
```