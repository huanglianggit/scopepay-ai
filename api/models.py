from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class ProjectInput(StrictModel):
    title: str = Field(min_length=2, max_length=100)
    client_name: str = Field(min_length=2, max_length=100)
    client_email: str = Field(default='', max_length=254)
    scope: str = Field(min_length=30, max_length=18000)
    base_cents: int = Field(ge=0, le=100000000, strict=True)
    due_date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')


class AnalyzeInput(StrictModel):
    message: str = Field(min_length=8, max_length=12000)


class AnalysisItem(StrictModel):
    title: str = Field(min_length=2, max_length=160)
    kind: Literal['added', 'changed', 'included', 'unclear']
    request_quote: str = Field(min_length=1, max_length=1500)
    scope_quote: str = Field(default='', max_length=1500)
    explanation: str = Field(min_length=3, max_length=1600)
    rate_id: Literal['language', 'booking', 'page', 'revision', 'rush', 'custom', 'none']
    question: str = Field(default='', max_length=500)


class AnalysisResult(StrictModel):
    summary: str = Field(min_length=3, max_length=1800)
    items: list[AnalysisItem] = Field(min_length=1, max_length=12)


class QuoteItem(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=2, max_length=160)
    selected: bool
    amount_cents: int = Field(ge=0, le=10000000, strict=True)
    resolution: str = Field(default='', max_length=1600)
    kind: Literal['added', 'changed', 'included', 'unclear'] | None = None


class PublishInput(StrictModel):
    items: list[QuoteItem] = Field(min_length=1, max_length=12)
    due_date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    note: str = Field(default='', max_length=2000)


class RespondInput(StrictModel):
    action: Literal['accept', 'decline']
    name: str = Field(min_length=2, max_length=100)
    note: str = Field(default='', max_length=1500)
    version: int = Field(ge=1)


class CaptureInput(StrictModel):
    order_id: str = Field(min_length=3, max_length=80, pattern=r'^[A-Za-z0-9-]+$')


class LoginInput(StrictModel):
    code: str = Field(default='', max_length=200)
