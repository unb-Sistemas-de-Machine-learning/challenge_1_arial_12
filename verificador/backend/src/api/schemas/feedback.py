from datetime import datetime
from pydantic import BaseModel, Field

class FeedbackRequest(BaseModel):
    veredicto_id: int = Field(description="Identificador único do veredicto avaliado.")
    util: bool = Field(description="Indica se o veredicto foi útil (positivo) ou não (negativo).")
    data_hora: datetime = Field(description="Data e hora em que o feedback foi enviado (com timezone).")

class FeedbackResponse(BaseModel):
    status: str
