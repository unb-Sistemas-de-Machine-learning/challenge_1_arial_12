# Plano — 009 Camada de persistência do Verificador

> Plano técnico da task #9. A spec registra o comportamento; este arquivo detalha como implementá-lo.

## 1. Abordagem

Duas tabelas declaradas com SQLAlchemy 2, acessadas por funções de repositório que expõem operações de domínio. O motor de conexão nasce no `lifespan` da aplicação e é descartado no encerramento; cada requisição recebe uma sessão própria por dependência, aberta dentro de um bloco de contexto que garante o fechamento mesmo quando a rota levanta exceção.

O schema passa a ser versionado por Alembic na variante assíncrona, com a URL lida de `get_settings()` em vez de escrita no `alembic.ini` — duas fontes de verdade para a mesma coisa divergem na primeira mudança.

Fora do backend, dois arquivos de infraestrutura mudam: o Compose ganha verificação de saúde no `db`, e a verificação automática de PR ganha um Postgres no job do backend, para os testes de integração rodarem lá também.

## 2. Arquivos tocados

| Arquivo | O que muda |
| :--- | :--- |
| `verificador/backend/src/core/database/models.py` | `Base`, `Veredito` e `Feedback` |
| `verificador/backend/src/core/database/session.py` | `criar_motor()`, `criar_fabrica_de_sessoes()` e a dependência `get_sessao()` |
| `verificador/backend/src/core/database/repositories.py` | Normalização, geração da chave e as três operações de domínio |
| `verificador/backend/src/core/database/__init__.py` | Exportação do que as outras camadas usam |
| `verificador/backend/src/main.py` | `lifespan` que cria e descarta o motor |
| `verificador/backend/alembic.ini` e `migrations/` | Versionamento do schema e migração inicial |
| `verificador/backend/requirements.txt` | `alembic` como dependência de execução |
| `verificador/backend/docker-compose.yml` | `healthcheck` no `db` e `depends_on` com condição |
| `.github/workflows/ci.yml` | Serviço de Postgres no job `backend` |
| `verificador/backend/src/tests/conftest.py` | URL do banco, decisão de pular sem banco e sessão isolada por transação |
| `verificador/backend/src/tests/**` | Testes de modelos, sessão, migrações, isolamento, repositórios e chave |

## 3. Contratos

```python
async def get_sessao(requisicao: Request) -> AsyncIterator[AsyncSession]: ...

def gerar_hash_do_trecho(trecho: str) -> str: ...

@dataclass(frozen=True)
class VereditoRegistrado:
    id: int
    resposta: dict

async def registrar_veredito(sessao, trecho, estado_veredito, resposta) -> VereditoRegistrado: ...
async def buscar_por_hash(sessao, hash_trecho) -> VereditoRegistrado | None: ...
async def registrar_feedback(sessao, veredito_id, util) -> int: ...
```

`buscar_por_hash` devolve a verificação **mais recente** com aquela chave, ou `None`. Nenhuma operação devolve objeto do SQLAlchemy.

## 4. Decisões técnicas

| Decisão | Alternativa descartada | Por quê |
| :--- | :--- | :--- |
| Chave indexada e **não** única | Restrição de unicidade | Com unicidade, verificação refeita após o cache vencer só poderia sobrescrever a linha, e feedbacks já dados apontariam para uma resposta que ninguém viu |
| Tabela `veredito` | `historico_busca`, nome da task | A linha guarda o resultado da análise, não só o registro da busca — divergência registrada na spec |
| Avaliação em tabela própria | Campo booleano dentro da verificação | Dois usuários avaliando a mesma verificação brigariam pelo mesmo campo |
| Chave derivada do trecho | Derivada da saída do Triador | Saída de LLM não se repete entre execuções; a chave nunca encontraria nada |
| Normalizar acento antes da chave | Comparar o texto cru | O mesmo acento tem duas codificações possíveis; sem normalizar, a mesma frase gera chaves diferentes conforme a página de origem |
| Não remover acento | Ignorar acentuação | "médula" e "medula" são perguntas diferentes |
| `resposta` como JSONB | Texto puro | Rejeita JSON malformado na escrita e permite consultar campo interno |
| `estado_veredito` duplicando dado do JSON | Ler sempre do JSON | Permite contar por estado sem abrir o JSON de cada linha |
| Estado como texto | Tipo enumerado do Postgres | Acrescentar um quarto estado exigiria migração |
| `commit` explícito no repositório | Commit automático ao fim da requisição | Gravaria também quando a rota decidiu não gravar |
| Isolamento por transação revertida | Recriar o schema a cada caso | Reverter é praticamente instantâneo |
| Um motor por caso de teste | Motor compartilhado pela sessão | Cada teste assíncrono roda em laço próprio; conexão aberta num laço não sobrevive ao seguinte |
| URL do Alembic vinda de `get_settings()` | Valor escrito no `alembic.ini` | Evita duas fontes de verdade |
| Verificação de saúde no Compose | Apenas `depends_on` | Há uma janela de ~6s entre o contêiner subir e o banco aceitar conexão |

## 5. Como testar

- **Unitários:** estrutura declarada das tabelas — nomes, tipos, índice sem unicidade, chave estrangeira e datas com fuso — lendo os metadados, sem banco. Normalização e geração da chave: equivalência, distinção e tamanho.
- **Integração:** contra Postgres real, isolado por transação revertida. Sessão fechada quando a rota falha, medindo o conjunto de conexões. Ciclo de aplicar e desfazer migrações. Divergência entre modelos e migrações. As três operações de domínio, incluindo duas verificações do mesmo trecho convivendo e duas avaliações opostas sobre a mesma verificação.
- **Sem banco:** a suíte não falha; os casos que precisam dele são pulados — exceto na verificação automática, onde banco ausente é defeito.
- **Eval:** não se aplica.

## 6. Riscos

- O `lifespan` **não pode** conectar ao banco na subida: `test_app_compose.py` instancia a aplicação com uma URL fictícia, e uma checagem de conectividade ali o quebraria por motivo sem relação aparente.
- Schema é o único artefato que acumula dado: corrigir coluna depois de a tabela ter conteúdo é migração de dado, não alteração de código.
- A migração gerada automaticamente precisa ser lida à mão, e ler não basta — o autoincremento da chave primária só aparece consultando o banco.
- Nenhuma rota de produção usa a sessão ainda; a camada está testada, mas não exercitada em uso real até a task #21.
