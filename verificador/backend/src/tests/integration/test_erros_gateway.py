"""Contrato HTTP e correlação dos erros do gateway."""

import logging
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from src.api.gateway.middlewares import ErroGateway
from src.api.schemas.erro import CodigoErro, Erro
from src.core.config import settings as settings_module
from src.core.config.settings import Settings


@pytest.fixture
def api(monkeypatch):
    custom = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://usuario:segredo@host-inexistente/teste",
        openai_api_key="sk-chave-de-teste",
        app_debug=True,
        cors_origins=["https://permitida.example"],
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: custom)
    from src.main import criar_app

    return criar_app()


def _conferir_erro(response, status: int, codigo: CodigoErro) -> None:
    assert response.status_code == status
    corpo = response.json()
    assert set(corpo) == {"codigo", "mensagem"}
    assert Erro.model_validate(corpo).codigo == codigo
    assert corpo["mensagem"]
    assert (
        str(UUID(response.headers["X-Correlation-ID"]))
        == response.headers["X-Correlation-ID"]
    )


def test_422_de_validacao_e_json_malformado_nao_expoem_entrada(api) -> None:
    with TestClient(api) as client:
        sem_trecho = client.post("/verificar", json={"url": "file:///arquivo-secreto"})
        json_malformado = client.post(
            "/verificar",
            content='{"trecho": "sk-chave-de-teste",',
            headers={"Content-Type": "application/json"},
        )

    for response in (sem_trecho, json_malformado):
        _conferir_erro(response, 422, CodigoErro.ENTRADA_INVALIDA)
        assert "arquivo-secreto" not in response.text
        assert "sk-chave-de-teste" not in response.text


def test_429_e_503_generico_nao_repassam_detail(api) -> None:
    @api.get("/limite")
    def limite():
        raise HTTPException(
            429, detail="detalhe privado", headers={"Retry-After": "60"}
        )

    @api.get("/servico")
    def servico():
        raise HTTPException(503, detail="token privado")

    with TestClient(api) as client:
        limitado = client.get("/limite")
        indisponivel = client.get("/servico")

    _conferir_erro(limitado, 429, CodigoErro.LIMITE_EXCEDIDO)
    assert limitado.headers["Retry-After"] == "60"
    _conferir_erro(indisponivel, 503, CodigoErro.SERVICO_INDISPONIVEL)
    assert "privado" not in limitado.text + indisponivel.text


def test_falhas_previstas_openalex_e_llm_tem_codigos_proprios(api) -> None:
    @api.get("/openalex")
    def openalex():
        raise ErroGateway(CodigoErro.OPENALEX_INDISPONIVEL)

    @api.get("/llm")
    def llm():
        raise ErroGateway(CodigoErro.LLM_TIMEOUT)

    with TestClient(api) as client:
        _conferir_erro(client.get("/openalex"), 503, CodigoErro.OPENALEX_INDISPONIVEL)
        _conferir_erro(client.get("/llm"), 504, CodigoErro.LLM_TIMEOUT)


def test_500_em_debug_oculta_detalhes_e_registra_rastreamento(api, caplog) -> None:
    @api.get("/quebra")
    def quebra():
        raise RuntimeError("sk-chave-de-teste em C:/codigo/arquivo.py DATABASE_URL")

    caplog.set_level(logging.ERROR, logger="verificador.gateway")
    with TestClient(api, raise_server_exceptions=False) as client:
        response = client.get(
            "/quebra",
            headers={
                "Origin": "https://permitida.example",
                "X-Correlation-ID": str(uuid4()),
            },
        )

    _conferir_erro(response, 500, CodigoErro.ERRO_INTERNO)
    assert response.json()["mensagem"] == "Ocorreu um erro interno."
    assert "sk-chave-de-teste" not in response.text + caplog.text
    assert "C:/codigo/arquivo.py" not in response.text
    assert "DATABASE_URL" not in response.text
    assert (
        response.headers["access-control-allow-origin"] == "https://permitida.example"
    )
    assert response.headers["X-Correlation-ID"] in caplog.text
    assert "X-Correlation-ID" in response.headers["access-control-expose-headers"]
    assert "test_erros_gateway.py" in caplog.text
    assert "in quebra" in caplog.text
    assert "[REDACTED]" in caplog.text


def test_404_405_resposta_generica_e_cors_negado_usam_contrato(api) -> None:
    @api.get("/resposta-generica")
    def resposta_generica():
        return PlainTextResponse("caminho privado", status_code=502)

    with TestClient(api) as client:
        _conferir_erro(
            client.get("/nao-existe"), 404, CodigoErro.RECURSO_NAO_ENCONTRADO
        )
        metodo = client.put("/health")
        _conferir_erro(metodo, 405, CodigoErro.METODO_NAO_PERMITIDO)
        assert metodo.headers["allow"] == "GET"
        _conferir_erro(client.get("/resposta-generica"), 502, CodigoErro.ERRO_INTERNO)
        preflight = client.options(
            "/verificar",
            headers={
                "Origin": "https://bloqueada.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        _conferir_erro(preflight, 400, CodigoErro.ERRO_REQUISICAO)


def test_id_de_correlacao_gerado_e_propagado_tambem_no_sucesso(api) -> None:
    recebido = str(uuid4())
    with TestClient(api) as client:
        sucesso = client.get("/health", headers={"X-Correlation-ID": recebido})
        substituido = client.get(
            "/health", headers={"X-Correlation-ID": "valor-invalido"}
        )

    assert sucesso.status_code == 200
    assert sucesso.headers["X-Correlation-ID"] == recebido
    assert (
        str(UUID(substituido.headers["X-Correlation-ID"]))
        == substituido.headers["X-Correlation-ID"]
    )
    assert substituido.headers["X-Correlation-ID"] != "valor-invalido"


def test_openapi_publica_schema_e_status_de_erro(api) -> None:
    with TestClient(api) as client:
        schema = client.get("/openapi.json").json()

    respostas = schema["paths"]["/verificar"]["post"]["responses"]
    for status in (422, 429, 500, 503, 504):
        assert (
            respostas[str(status)]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/Erro"
        )
    assert set(schema["components"]["schemas"]["CodigoErro"]["enum"]) == {
        codigo.value for codigo in CodigoErro
    }
