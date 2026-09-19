# Plano — 006 Configuração centralizada do backend

> Plano aplicado ao stub atual. A spec permanece em revisão formal antes do PR.

## 1. Abordagem

Implementar `Settings` com `pydantic-settings` e um `get_settings()` com `lru_cache`. Resolver o caminho do `.env` a partir da pasta do backend, não do diretório de execução. Validar os campos obrigatórios na construção do aplicativo ativo, antes de servir requisições, sem tentar abrir conexão com serviços externos. Usar `CORS_ORIGINS` na configuração do middleware, preservando `['*']` como padrão.

## 2. Arquivos tocados

| Arquivo | O que muda |
| :--- | :--- |
| `verificador/backend/src/core/config/settings.py` | `Settings`, validação, proteção de segredos e `get_settings()` |
| `verificador/backend/main.py` | Obter a configuração no início da criação do app e consumir `APP_DEBUG` e `CORS_ORIGINS` |
| `verificador/backend/src/tests/unit/test_settings.py` | Casos de configuração válida, obrigatória ausente, segredo e cache |
| `verificador/backend/src/tests/integration/test_startup_settings.py` | Falha de inicialização antes de qualquer requisição |
| `verificador/backend/.env.example` | Documentar `CORS_ORIGINS` como lista JSON, por exemplo `CORS_ORIGINS='["*"]'` |
| `verificador/README.md` | Explicar a criação do `.env` e a validação antecipada de `DATABASE_URL` |

## 3. Contratos

```python
class Settings(BaseSettings):
    app_debug: bool = False
    openai_api_key: SecretStr | None = None
    database_url: SecretStr  # obrigatório; espaços em branco não são valor válido
    openalex_mailto: str | None = None
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

@lru_cache
def get_settings() -> Settings: ...
```

Os nomes Python em minúsculas correspondem às variáveis `APP_DEBUG`, `OPENAI_API_KEY`, `DATABASE_URL`, `OPENALEX_MAILTO` e `CORS_ORIGINS`. Campos opcionais vazios são normalizados para `None`. A configuração falha por ausência ou vazio de `DATABASE_URL`, mas não por indisponibilidade do banco. Consumidores da URL do banco obtêm o valor real explicitamente com `get_secret_value()`. `CORS_ORIGINS` é uma lista JSON no ambiente; por exemplo, `'["https://example.com"]'`.

`get_settings.cache_clear()` permite isolar testes; `Settings(_env_file=None, ...)` permite montar uma configuração sem ler o `.env` real. Consumidores futuros devem obter a instância por `get_settings()` em vez de instanciar `Settings` novamente.

## 4. Decisões técnicas

| Decisão | Alternativa descartada | Por quê |
| :--- | :--- | :--- |
| `BaseSettings` e `SettingsConfigDict` | Ler `os.getenv` em cada módulo | Mantém tipagem, precedência de fontes e validação em um só lugar |
| Caminho absoluto do `.env` derivado de `settings.py` | `.env` relativo ao CWD | Permite executar testes e Uvicorn de diferentes diretórios |
| `SecretStr` para chave e URL do banco, com `hide_input_in_errors=True` | `str` comum para segredos | Reduz vazamento em representações e erros |
| `lru_cache` com limpeza explícita em testes | Instância global criada no import do módulo | Evita leituras repetidas e permite sobrescrita controlada |
| `DATABASE_URL` obrigatória, mas sem conexão na validação | Testar o banco na inicialização | A task exige presença, não disponibilidade do serviço |
| `CORS_ORIGINS` em `Settings` | Manter `allow_origins=["*"]` fixo no stub | É configuração da aplicação e pode variar por ambiente sem mudar código |
| Porta fora de `Settings` | Criar `APP_PORT` | Uvicorn já possui opção própria de porta; duplicá-la cria duas fontes de verdade |

## 5. Como testar

- **Unitários:** usar `Settings(_env_file=None, ...)` e `monkeypatch`/`cache_clear()`; cobrir os cinco campos, bool, ausência/vazio/espaços em `DATABASE_URL`, segredos não expostos, `CORS_ORIGINS` padrão e leitura de lista JSON. Nenhum teste usa rede ou `.env` real.
- **Integração:** construir/importar a aplicação com `DATABASE_URL` ausente e confirmar falha antes de qualquer cliente HTTP; repetir com configuração válida e confirmar criação do app. Verificar que uma origem configurada recebe o cabeçalho CORS e uma não configurada não o recebe.
- **Eval:** não se aplica.

## 6. Riscos

- O `.env.example` contém chave de OpenAI e e-mail vazios. Torná-los obrigatórios agora quebraria o stub; a spec os mantém opcionais até a etapa de integração.
- Validar no import do ponto de entrada ativo pode exigir que testes antigos forneçam configuração antes de importar a aplicação. Ajustar fixtures sem recorrer ao `.env` pessoal.
- A task #7 trocará o ponto de entrada. Reutilizar `get_settings()` na fábrica futura, sem repetir a validação em cada requisição.
- O padrão `['*']` preserva o comportamento atual, mas não constitui uma política restritiva para produção. A política de origens permitidas deve ser definida pelo ambiente de implantação.
