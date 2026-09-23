"""Tabelas do Verificador: o resultado de cada verificação e as avaliações."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Tamanho do hexadecimal de um SHA-256. Fixo, então cabe num índice sem susto.
TAMANHO_HASH = 64

ESTADOS_VEREDITO = ("sustenta", "exagera", "nada_encontrado")


class Base(DeclarativeBase):
    """Base comum; é o que as migrações leem para descobrir o schema."""


class Veredito(Base):
    """Uma linha por verificação feita — não por trecho distinto.

    O hash é indexado mas **não** é único: verificação repetida depois do cache
    vencer gera linha nova. Com unicidade, a linha existente teria de ser
    sobrescrita, e os feedbacks já dados passariam a apontar para uma resposta
    que ninguém avaliou.
    """

    __tablename__ = "veredito"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Derivado do trecho normalizado, nunca da saída de um agente de IA: LLM não
    # devolve o mesmo texto duas vezes, e a chave jamais encontraria nada.
    hash_trecho: Mapped[str] = mapped_column(String(TAMANHO_HASH), nullable=False)
    trecho_avaliado: Mapped[str] = mapped_column(Text, nullable=False)
    # Repete um campo que já existe dentro de `resposta`, de propósito: permite
    # contar quantos "exagera" receberam 👎 sem abrir o JSON de cada linha.
    estado_veredito: Mapped[str] = mapped_column(Text, nullable=False)
    resposta: Mapped[dict] = mapped_column(JSONB, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        # timezone=True para o Postgres guardar um instante absoluto; o relógio
        # do banco é a fonte, e não o da máquina que roda a aplicação.
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="veredito")

    __table_args__ = (Index("ix_veredito_hash_trecho", "hash_trecho"),)


class Feedback(Base):
    """Uma linha por avaliação. Várias podem existir sobre o mesmo veredito."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    veredito_id: Mapped[int] = mapped_column(
        # Chave estrangeira de verdade: o banco passa a recusar avaliação órfã.
        ForeignKey("veredito.id"),
        nullable=False,
    )
    util: Mapped[bool] = mapped_column(Boolean, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    veredito: Mapped[Veredito] = relationship(back_populates="feedbacks")

    __table_args__ = (Index("ix_feedback_veredito_id", "veredito_id"),)
