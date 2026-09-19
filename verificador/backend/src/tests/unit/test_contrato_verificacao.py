"""Valida os modelos e a paridade com o contrato da extensão."""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.api.schemas.verificacao import Estado, Estudo, Pedido, Veredito

TIPOS_TS = Path(__file__).resolve().parents[4] / "extensao" / "tipos.ts"


def _interface_fields(source: str, name: str) -> dict[str, str]:
    match = re.search(rf"export interface {name}\s*\{{([^}}]*)\}}", source)
    assert match, f"Interface {name} ausente em tipos.ts"
    return dict(re.findall(r"\b(\w+)\s*:\s*([^;]+);", match.group(1)))


def test_pedido_aceita_url_file_e_sem_url() -> None:
    assert (
        Pedido(trecho="texto", url="file:///pagina-teste.html").url
        == "file:///pagina-teste.html"
    )
    assert Pedido(trecho="texto").url is None


def test_pedido_exige_trecho_string_sem_limite_de_comprimento_definido() -> None:
    with pytest.raises(ValidationError):
        Pedido.model_validate({"url": "file:///pagina-teste.html"})
    with pytest.raises(ValidationError):
        Pedido.model_validate({"trecho": 123})
    assert Pedido(trecho="").trecho == ""
    assert len(Pedido(trecho="x" * 100_000).trecho) == 100_000


def test_estado_aceita_apenas_os_tres_valores_do_contrato() -> None:
    assert {estado.value for estado in Estado} == {
        "sustenta",
        "exagera",
        "nada_encontrado",
    }
    with pytest.raises(ValidationError):
        Veredito.model_validate(
            {
                "estado": "desconhecido",
                "estudo": None,
                "termos": [],
                "justificativa": "teste",
            }
        )


def test_estudo_aceita_null_mas_exige_campos_presentes() -> None:
    estudo = Estudo(titulo="Exemplo", ano=None, doi=None, retratado=False)
    assert estudo.ano is None and estudo.doi is None
    with pytest.raises(ValidationError):
        Estudo.model_validate({"titulo": "Exemplo", "retratado": False})


def test_veredito_aceita_estudo_null() -> None:
    veredito = Veredito(
        estado=Estado.NADA_ENCONTRADO,
        estudo=None,
        termos=[],
        justificativa="Sem estudo",
    )
    assert veredito.model_dump(mode="json")["estudo"] is None


def test_campos_dos_modelos_correspondem_ao_typescript() -> None:
    source = TIPOS_TS.read_text(encoding="utf-8")
    assert _interface_fields(source, "Estudo") == {
        "titulo": "string",
        "ano": "number | null",
        "doi": "string | null",
        "retratado": "boolean",
    }
    assert _interface_fields(source, "Veredito") == {
        "estado": "Estado",
        "estudo": "Estudo | null",
        "termos": "string[]",
        "justificativa": "string",
    }
    assert set(Estudo.model_fields) == set(_interface_fields(source, "Estudo"))
    assert set(Veredito.model_fields) == set(_interface_fields(source, "Veredito"))
    assert all(field.is_required() for field in Estudo.model_fields.values())
    assert all(field.is_required() for field in Veredito.model_fields.values())


def test_valores_de_estado_correspondem_ao_typescript() -> None:
    source = TIPOS_TS.read_text(encoding="utf-8")
    match = re.search(r"export type Estado\s*=\s*([^;]+);", source)
    assert match, "Tipo Estado ausente em tipos.ts"
    valores_ts = set(re.findall(r'"([^"]+)"', match.group(1)))
    assert valores_ts == {estado.value for estado in Estado}
