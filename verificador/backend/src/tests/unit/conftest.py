"""Nenhum teste unitário abre soquete — verificado, e não prometido.

A spec 002 afirma que os testes unitários não chamam a rede. Isso era só uma
convenção até um teste passar a fazer requisição de verdade sem ninguém notar:
ele continuou verde, porque o `.env` da máquina tinha o campo vazio e a chamada
falhava antes de sair. Verde por acidente é pior do que vermelho.

Daqui em diante, tentar conectar dentro de `src/tests/unit/` estoura na hora,
apontando para a linha que tentou. Quem precisa de rede de verdade está em
`src/tests/integration/`, sob a marca `rede`.
"""

import socket

import pytest


class TentouUsarARede(RuntimeError):
    """Um teste unitário tentou abrir conexão."""


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch: pytest.MonkeyPatch) -> None:
    def recusar(self: socket.socket, endereco: object, *_resto: object) -> None:
        # Permite 127.0.0.1 para que o ProactorEventLoop do asyncio no Windows possa criar seu self-pipe.
        if isinstance(endereco, tuple) and endereco[0] == "127.0.0.1":
            return socket._real_connect(self, endereco, *_resto)  # type: ignore
        raise TentouUsarARede(
            f"teste unitário tentou conectar em {endereco!r}. Use "
            "httpx.MockTransport com as fixtures de src/tests/fixtures/, ou "
            "mova o teste para integration/ com a marca 'rede'."
        )

    # Precisamos salvar o connect original para chamar quando for localhost
    socket._real_connect = socket.socket.connect  # type: ignore

    monkeypatch.setattr(socket.socket, "connect", recusar)
    monkeypatch.setattr(socket.socket, "connect_ex", recusar)
