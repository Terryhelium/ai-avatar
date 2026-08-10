from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import TypeAdapter, ValidationError

from kiosk_app.config import Settings, load_settings
from kiosk_app.models import (
    ChatRequest,
    ChatResponse,
    ChatTurn,
    HealthResponse,
    MetahumanOfferRequest,
    MetahumanOfferResponse,
    ServiceStatus,
    VoiceChatResponse,
)
from kiosk_app.services import Orchestrator, ServiceError


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    http_client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)
    app.state.settings = settings
    app.state.http_client = http_client
    app.state.orchestrator = Orchestrator(settings, http_client)
    try:
        yield
    finally:
        await http_client.aclose()


app = FastAPI(title="Reception Kiosk", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _static_dir() -> Path:
    settings: Settings = getattr(app.state, "settings", load_settings())
    return Path(settings.static_dir).resolve()


app.mount("/static", StaticFiles(directory=_static_dir()), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(_static_dir() / "index.html")


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    orchestrator: Orchestrator = app.state.orchestrator
    statuses = await orchestrator.health()
    return HealthResponse(
        services=[
            ServiceStatus(
                name=status["name"],
                ok=bool(status["ok"]),
                detail=str(status["detail"]),
            )
            for status in statuses
        ]
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    orchestrator: Orchestrator = app.state.orchestrator
    try:
        reply = await orchestrator.reply(
            request.question,
            history=request.history,
            synthesize_audio=request.synthesize_audio,
        )
    except httpx.HTTPError as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        raise HTTPException(status_code=502, detail=f"Upstream HTTP error: {detail}") from exc
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ChatResponse(
        answer=reply.answer,
        audio_base64=reply.audio_base64,
        audio_mime_type=reply.audio_mime_type,
        retrieval_chunks=reply.retrieval_chunks,
        retrieval_status=reply.retrieval_status,
        retrieval_detail=reply.retrieval_detail,
        timings_ms=reply.timings_ms,
        metahuman_dispatched=reply.metahuman_dispatched,
    )


@app.post("/api/voice-chat", response_model=VoiceChatResponse)
async def voice_chat(
    audio: UploadFile = File(...),
    history: str = Form("[]"),
    synthesize_audio: bool = Form(True),
) -> VoiceChatResponse:
    orchestrator: Orchestrator = app.state.orchestrator
    try:
        history_items = TypeAdapter(list[ChatTurn]).validate_python(json.loads(history))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid history payload: {exc}") from exc

    try:
        audio_bytes = await audio.read()
        transcript = await orchestrator.transcribe(audio_bytes, wav_name=audio.filename or "microphone")
        reply = await orchestrator.reply(
            transcript,
            history=history_items,
            synthesize_audio=bool(synthesize_audio),
        )
    except httpx.HTTPError as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        raise HTTPException(status_code=502, detail=f"Upstream HTTP error: {detail}") from exc
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return VoiceChatResponse(
        transcript=transcript,
        answer=reply.answer,
        audio_base64=reply.audio_base64,
        audio_mime_type=reply.audio_mime_type,
        retrieval_chunks=reply.retrieval_chunks,
        retrieval_status=reply.retrieval_status,
        retrieval_detail=reply.retrieval_detail,
        timings_ms=reply.timings_ms,
        metahuman_dispatched=reply.metahuman_dispatched,
    )


@app.post("/api/metahuman/offer", response_model=MetahumanOfferResponse)
async def metahuman_offer(request: MetahumanOfferRequest) -> MetahumanOfferResponse:
    orchestrator: Orchestrator = app.state.orchestrator
    try:
        answer = await orchestrator.metahuman_offer(
            {
                "sdp": request.sdp,
                "type": request.type,
            }
        )
    except httpx.HTTPError as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        raise HTTPException(status_code=502, detail=f"Upstream HTTP error: {detail}") from exc
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return MetahumanOfferResponse(sdp=answer["sdp"], type=answer["type"])
