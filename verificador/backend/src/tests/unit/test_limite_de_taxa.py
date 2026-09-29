"""Contador de janela fixa isolado, com relógio controlável pelo teste."""

from src.api.gateway.middlewares import ContadorDeJanelaFixa


class RelogioFalso:
    def __init__(self, agora: float = 0.0) -> None:
        self._agora = agora

    def avancar(self, segundos: float) -> None:
        self._agora += segundos

    def __call__(self) -> float:
        return self._agora


def test_permite_ate_o_limite_e_nega_a_seguinte() -> None:
    relogio = RelogioFalso()
    contador = ContadorDeJanelaFixa(limite=2, janela_segundos=10, relogio=relogio)

    assert contador.registrar("origem-a") == (True, 0)
    assert contador.registrar("origem-a") == (True, 0)
    permitida, restante = contador.registrar("origem-a")
    assert permitida is False
    assert restante == 10


def test_janela_expira_e_a_mesma_chave_volta_a_ser_aceita() -> None:
    relogio = RelogioFalso()
    contador = ContadorDeJanelaFixa(limite=1, janela_segundos=5, relogio=relogio)

    assert contador.registrar("origem-a") == (True, 0)
    assert contador.registrar("origem-a")[0] is False

    relogio.avancar(5)
    assert contador.registrar("origem-a") == (True, 0)


def test_chaves_diferentes_nao_se_afetam() -> None:
    relogio = RelogioFalso()
    contador = ContadorDeJanelaFixa(limite=1, janela_segundos=10, relogio=relogio)

    assert contador.registrar("origem-a") == (True, 0)
    assert contador.registrar("origem-a")[0] is False
    assert contador.registrar("origem-b") == (True, 0)


def test_segundos_restantes_arredondam_para_cima() -> None:
    relogio = RelogioFalso()
    contador = ContadorDeJanelaFixa(limite=1, janela_segundos=10, relogio=relogio)

    contador.registrar("origem-a")
    relogio.avancar(7.2)
    _, restante = contador.registrar("origem-a")
    assert restante == 3
