from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=4)
    synthesize_audio: bool = True


class RetrievalChunk(BaseModel):
    content: str
    score: float | None = None


RetrievalStatus = Literal["hit", "miss", "error", "disabled"]


class ChatResponse(BaseModel):
    answer: str
    audio_base64: str | None = None
    audio_mime_type: str | None = None
    retrieval_chunks: list[RetrievalChunk] = Field(default_factory=list)
    retrieval_status: RetrievalStatus = "miss"
    retrieval_detail: str | None = None
    timings_ms: dict[str, int] = Field(default_factory=dict)
    metahuman_dispatched: bool = False


class VoiceChatResponse(ChatResponse):
    transcript: str


class ServiceStatus(BaseModel):
    name: str
    ok: bool
    detail: str


class HealthResponse(BaseModel):
    services: list[ServiceStatus]


class MetahumanOfferRequest(BaseModel):
    sdp: str = Field(min_length=1)
    type: str = Field(min_length=1)


class MetahumanOfferResponse(BaseModel):
    sdp: str
    type: str
