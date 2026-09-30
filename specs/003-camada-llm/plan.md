# Plano - 003 Camada de acesso a LLM

## 1. Abordagem

A camada tem duas peças. O **provedor** só sabe fazer uma requisição e
classificar a falha. O **`ClienteLLM`** cuida do resto: timeout, repetição,
validação por schema e log. Os agentes só enxergam o `ClienteLLM`. O
`DubleLLM` ocupa o lugar do provedor nos testes, então timeout, repetição,
validação e log rodam de verdade mesmo sem rede.

É o mesmo molde do cliente da OpenAlex (`src/services/openalex.py`): erros de
domínio próprios, falha transitória separada da definitiva, e construção a
partir das configurações.

```text
agente ──> ClienteLLM.gerar(prompt, schema)
              │  timeout total, repetição, validação, log
              ▼
           ProvedorLLM.completar(...)   ← protocolo
              ├── ProvedorCompativelComOpenAI  (Groq ou Gemini, produção)
              └── DubleLLM                     (testes)
```

## 2. Arquivos tocados

| Arquivo | O que muda |
| :--- | :--- |
| `verificador/backend/src/services/llm.py` | novo: protocolo, provedor real, `ClienteLLM`, erros e dependência |
| `verificador/backend/src/tests/dubles/llm.py` | novo: `DubleLLM` |
| `verificador/backend/src/core/config/settings.py` | troca `openai_api_key` pelos campos `llm_*` |
| `verificador/backend/.env.example` | variáveis `LLM_*` |
| `verificador/backend/src/api/schemas/erro.py` | código `llm_indisponivel` |
| `verificador/backend/src/api/gateway/middlewares.py` | traduz `ErroLLM` para o contrato da `011`; redação da chave nova |
| `verificador/backend/src/main.py` | fecha o cliente compartilhado no encerramento |
| `verificador/extensao/tipos.ts`, `mensagens-erro.ts` | mensagem de `llm_indisponivel` |
| `verificador/backend/src/tests/unit/test_llm.py` | novo |
| `verificador/backend/src/tests/integration/test_llm_gateway.py` | novo |
| `verificador/README.md` | seção da camada e nova linha na tabela de erros |

## 3. Contratos

```python
# src/services/llm.py
T = TypeVar("T", bound=BaseModel)

@dataclass(frozen=True)
class RespostaDoProvedor:
    texto: str
    modelo: str
    tokens_entrada: int | None
    tokens_saida: int | None

class ProvedorLLM(Protocol):
    nome: str
    modelo: str
    async def completar(
        self, *, sistema: str, prompt: str, nome_schema: str, schema_json: dict
    ) -> RespostaDoProvedor: ...
    async def fechar(self) -> None: ...

class ErroLLM(RuntimeError): ...
class LLMTempoEsgotado(ErroLLM): ...
class LLMIndisponivel(ErroLLM): ...
class LLMRecusouOPedido(LLMIndisponivel): ...   # 4xx: não adianta repetir
class RespostaInvalidaDoLLM(ErroLLM): ...
class FalhaTransitoria(Exception): ...          # o provedor sinaliza "vale repetir"

class ClienteLLM:
    def __init__(self, provedor: ProvedorLLM, *, timeout_segundos=15.0,
                 max_tentativas=2, ...): ...
    @classmethod
    def a_partir_das_configuracoes(cls) -> "ClienteLLM": ...
    async def gerar(self, prompt: str, schema: type[T], *,
                    sistema: str | None = None,
                    timeout_segundos: float | None = None) -> T: ...

def obter_cliente_llm() -> ClienteLLM: ...     # dependência do FastAPI
```

Uso em um agente:

```python
class Variacoes(BaseModel):
    buscas: list[str]

async def triar(trecho: str, llm: ClienteLLM) -> Variacoes:
    return await llm.gerar(f"Gere buscas para: {trecho}", Variacoes)
```

Linha de log (logger `verificador.llm`):

```text
llm provedor=groq modelo=openai/gpt-oss-20b resultado=ok latencia_ms=842 tokens_entrada=312 tokens_saida=45 tentativas=1
```

Configuração (`.env`):

| Variável | Padrão | Observação |
| :--- | :--- | :--- |
| `LLM_PROVEDOR` | `groq` | `groq` ou `gemini` |
| `LLM_API_KEY` | vazio | obrigatória só quando a camada é usada |
| `LLM_MODELO` | vazio | vazio usa o padrão do provedor |
| `LLM_TIMEOUT_SEGUNDOS` | `15` | tempo total da chamada, tentativas incluídas |
| `LLM_MAX_TENTATIVAS` | `2` | de 1 a 5 |
| `LLM_FORMATO_JSON` | `json_schema` | `json_object` para modelos sem saída estruturada |

| Provedor | `base_url` | Modelo padrão |
| :--- | :--- | :--- |
| `groq` | `https://api.groq.com/openai/v1` | `openai/gpt-oss-20b` |
| `gemini` | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-3.5-flash` |

## 4. Decisões técnicas

| Decisão | Alternativa descartada | Por quê |
| :--- | :--- | :--- |
| Groq e Gemini pela biblioteca `openai` | SDK próprio de cada provedor | os dois aceitam o formato da OpenAI; é uma dependência só, e ela já estava no projeto |
| Provedor escolhido por `.env` | amarrar a um provedor no código | trocar de provedor ou de modelo vira configuração, sem mudar código |
| Timeout total por chamada (`asyncio.timeout`) | timeout por tentativa | o que importa é quanto o leitor espera; com timeout por tentativa, 2 tentativas dobrariam a espera |
| Repetição feita pela camada, com `max_retries=0` no SDK | deixar o SDK repetir | a camada precisa contar tentativas para o log e respeitar o prazo total |
| Resposta inválida não é repetida | repetir até acertar | gasta cota gratuita, e o mesmo prompt costuma errar do mesmo jeito; o agente decide se tenta de novo |
| `json_schema` por padrão, com o schema também no prompt | só `json_object` | os modelos padrão dos dois provedores aceitam saída estruturada; o schema no prompt garante o formato no modo `json_object` |
| Novo código `llm_indisponivel` (503) | reaproveitar `servico_indisponivel` | a extensão consegue dizer ao leitor que o problema é na análise, como já faz com `openalex_indisponivel` |
| Resposta inválida vira `llm_indisponivel` | `erro_interno` (500) | não é defeito nosso: o provedor respondeu fora do combinado |
| `openai_api_key` renomeada para `llm_api_key` | manter o nome | uma chave da Groq em `OPENAI_API_KEY` confundiria quem lê o `.env` |
| Dublê no lugar do provedor | dublê no lugar do `ClienteLLM` | assim o timeout, a repetição e a validação rodam de verdade nos testes |

## 5. Como testar

- **Unit (`test_llm.py`):** o `DubleLLM` cobre sucesso, JSON inválido, schema
  errado, lentidão (timeout), falha transitória, recusa definitiva e log. O
  provedor real é testado com `httpx.MockTransport`: a biblioteca `openai`
  roda de verdade e só o soquete é dublê, como no teste da OpenAlex.
- **Integração (`test_llm_gateway.py`):** uma rota de teste recebe o cliente
  por `Depends(obter_cliente_llm)`, o teste injeta o dublê e confere os
  corpos 503 e 504 do contrato.
- **Eval:** não se aplica; fica com os agentes.

## 6. Riscos

- **Modelos gratuitos mudam ou saem do ar.** O modelo é configurável, e o
  padrão fica em um só lugar (`PROVEDORES`).
- **Cota da camada gratuita.** Sob uso intenso, o provedor responde 429. A
  camada repete dentro do prazo e depois devolve `llm_indisponivel`.
- **Modelo sem saída estruturada.** Alguns modelos da Groq só aceitam
  `json_object`. Nesse caso, `LLM_FORMATO_JSON=json_object`.
