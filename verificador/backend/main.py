"""Back-end stub da Fase 01 — responde sempre o mesmo veredito mock.

Na Fase 02 este arquivo passa a consultar o OpenAlex de verdade; o contrato
JSON (entrada e saida) nao muda, entao a extensao continua igual.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.core.config.settings import get_settings

settings = get_settings()
app = FastAPI(title="Verificador Cientifico — stub Fase 01", debug=settings.app_debug)

# Por padrao liberamos tudo: a origem da extensao muda entre
# chrome-extension://<id> e moz-extension://<uuid>, e o uuid do Firefox
# e diferente a cada perfil.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Pedido(BaseModel):
    trecho: str
    url: str | None = None


@app.get("/saude")
def saude():
    return {"ok": True}


@app.post("/verificar")
def verificar(p: Pedido):
    print(f"[verificar] url={p.url}")
    print(f"[verificar] trecho={p.trecho!r}")
    return {
        "estado": "exagera",
        "estudo": {
            "titulo": "(mock) Estudo de exemplo",
            "ano": 2019,
            "doi": "10.0000/mock",
            "retratado": False,
        },
        "termos": ["polylaminin", "spinal cord injury", "regeneration"],
        "justificativa": "(mock) Resposta de teste — a IA entra na Fase 04.",
    }
