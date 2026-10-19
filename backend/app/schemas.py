from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    transaction_id: str = Field(min_length=1, max_length=128)
    source_account: str = Field(min_length=1, max_length=128)
    destination_account: str = Field(min_length=1, max_length=128)
    amount: float = Field(gt=0, allow_inf_nan=False)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    timestamp: datetime
    channel: str | None = Field(default=None, max_length=64)
    status: str = Field(default="completed", max_length=32)


class DatasetInfo(BaseModel):
    dataset_id: str
    name: str
    source: str
    transaction_count: int
    account_count: int
    created_at: datetime
    warnings: list[str] = []
    rejected_count: int = 0


class AnalysisRequest(BaseModel):
    dataset_id: str
    config: dict[str, Any] = Field(default_factory=dict)


class AnalysisStatus(BaseModel):
    analysis_id: str
    dataset_id: str
    status: str
    created_at: datetime
    summary: dict[str, Any] | None = None
    error: str | None = None


class PatternFeedbackRequest(BaseModel):
    pattern_id: str = Field(min_length=1, max_length=128)
    feedback: Literal["false_positive", "reviewed"]
