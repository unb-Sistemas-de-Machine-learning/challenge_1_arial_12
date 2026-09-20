"""Rotas técnicas do gateway; as rotas de negócio chegam em B05."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["health"])
def health() -> dict[str, bool]:
    return {"ok": True}
