from __future__ import annotations

import json
import os
import time
import uuid
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


API_KEY = _env("OPENAI_PROXY_API_KEY", "ragflow-proxy-local")
RAGFLOW_URL = _env("RAGFLOW_URL", "http://10.19.26.148:19003/api/v1/retrieval")
RAGFLOW_TOKEN = _env("RAGFLOW_TOKEN")
RAGFLOW_DATASET_IDS = [
    item.strip() for item in _env("RAGFLOW_DATASET_IDS").split(",") if item.strip()
]
RAGFLOW_TOP_K = int(_env("RAGFLOW_TOP_K", "3"))
OLLAMA_URL = _env("OLLAMA_URL", "http://10.19.26.153:11434/v1/chat/completions")
OLLAMA_MODEL = _env("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_TEMPERATURE = float(_env("OLLAMA_TEMPERATURE", "0.3"))
OLLAMA_MAX_TOKENS = int(_env("OLLAMA_MAX_TOKENS", "1200"))
MODEL_ID = _env("MODEL_ID", "ragflow-qa")
SYSTEM_PROMPT = _env(
    "SYSTEM_PROMPT",
    (
        "你是档案馆知识库问答助手。"
        "优先基于知识库内容作答，回答简洁、准确、自然。"
        "如果知识库不能支持结论，就明确说明无法从知识库确认，不要编造。"
    ),
)
REQUEST_TIMEOUT = float(_env("REQUEST_TIMEOUT_SECONDS", "60"))

app = FastAPI(title="OpenWebUI RAGFlow OpenAI Proxy")


class ChatMessage(BaseModel):
    role: str
    content: str | list[dict] | None = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


class RetrievalChunk(BaseModel):
    index: int
    content: str
    score: float | None = None


def _check_auth(authorization: str | None) -> None:
    if authorization != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def _message_text(content: str | list[dict] | None) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return ""


async def _retrieve(
    question: str,
    client: httpx.AsyncClient,
) -> tuple[list[RetrievalChunk], str, str | None]:
    if not RAGFLOW_TOKEN or not RAGFLOW_DATASET_IDS:
        return [], "disabled", "missing-config"

    try:
        response = await client.post(
            RAGFLOW_URL,
            headers={
                "Authorization": f"Bearer {RAGFLOW_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "question": question,
                "dataset_ids": RAGFLOW_DATASET_IDS,
                "top_k": RAGFLOW_TOP_K,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        return [], "error", detail

    if payload.get("code") != 0:
        detail = str(payload.get("message") or f"code:{payload.get('code')}")
        return [], "error", detail

    chunks: list[RetrievalChunk] = []
    for idx, item in enumerate(payload.get("data", {}).get("chunks", []), start=1):
        text = str(item.get("content") or "").strip()
        if text:
            score = item.get("similarity")
            chunks.append(
                RetrievalChunk(
                    index=idx,
                    content=text,
                    score=float(score) if isinstance(score, (int, float)) else None,
                )
            )

    if chunks:
        return chunks, "hit", None
    return [], "miss", None


async def _answer(
    messages: list[ChatMessage],
    client: httpx.AsyncClient,
) -> tuple[str, str, str | None, list[RetrievalChunk]]:
    user_messages = [item for item in messages if item.role == "user" and _message_text(item.content)]
    question = _message_text(user_messages[-1].content) if user_messages else ""
    retrieval_chunks, retrieval_status, retrieval_detail = await _retrieve(question, client)

    system_prompt = SYSTEM_PROMPT
    if retrieval_chunks:
        context = "\n\n".join(
            f"[{chunk.index}] {chunk.content}" for chunk in retrieval_chunks[:3]
        )[:3000]
        system_prompt += (
            "\n\n以下是知识库检索结果，请优先基于它们回答。"
            "如果使用了知识库内容，请尽量在相关句子后标注引用编号，如 [1]、[2]。\n"
            f"---\n{context}\n---"
        )
    elif retrieval_status == "error" and retrieval_detail:
        system_prompt += (
            "\n\n注意：本次知识库检索失败。"
            f"失败信息：{retrieval_detail}。"
            "你可以基于常识补充回答，但必须明确说明无法从知识库确认。"
        )

    ollama_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for item in messages:
        text = _message_text(item.content)
        if text:
            ollama_messages.append({"role": item.role, "content": text})

    response = await client.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "messages": ollama_messages,
            "temperature": OLLAMA_TEMPERATURE,
            "max_tokens": OLLAMA_MAX_TOKENS,
            "stream": False,
            "user": "open-webui-rag-proxy",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    try:
        answer = payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Invalid Ollama response") from exc

    return (
        _render_answer(answer, retrieval_status, retrieval_detail, retrieval_chunks),
        retrieval_status,
        retrieval_detail,
        retrieval_chunks,
    )


def _render_answer(
    answer: str,
    retrieval_status: str,
    retrieval_detail: str | None,
    retrieval_chunks: list[RetrievalChunk],
) -> str:
    status_text = {
        "hit": "知识库已命中",
        "miss": "知识库未命中",
        "error": "知识库检索失败",
        "disabled": "知识库未启用",
    }.get(retrieval_status, retrieval_status)

    lines = [answer.strip(), "", "---", f"知识库状态：{status_text}"]

    if retrieval_status == "error" and retrieval_detail:
        lines.append(f"检索说明：{retrieval_detail}")

    if retrieval_chunks:
        lines.extend(["", "参考出处："])
        for chunk in retrieval_chunks[:3]:
            snippet = " ".join(chunk.content.split())
            if len(snippet) > 180:
                snippet = snippet[:180].rstrip() + "..."
            if chunk.score is None:
                lines.append(f"{chunk.index}. {snippet}")
            else:
                lines.append(f"{chunk.index}. {snippet} (score={chunk.score:.3f})")

    return "\n".join(lines).strip()


def _chunk_text(text: str, chunk_size: int = 32) -> list[str]:
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)] or [""]


async def _stream_response(answer: str, request_id: str) -> AsyncIterator[str]:
    created = int(time.time())
    for chunk in _chunk_text(answer):
        payload = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": MODEL_ID,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": chunk},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    final_payload = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": MODEL_ID,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models(authorization: str | None = Header(default=None)) -> JSONResponse:
    _check_auth(authorization)
    return JSONResponse(
        {
            "object": "list",
            "data": [
                {
                    "id": MODEL_ID,
                    "object": "model",
                    "created": 0,
                    "owned_by": "nbdag",
                }
            ],
        }
    )


@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    authorization: str | None = Header(default=None),
):
    _check_auth(authorization)

    async with httpx.AsyncClient() as client:
        answer, retrieval_status, retrieval_detail, retrieval_chunks = await _answer(
            request.messages,
            client,
        )

    request_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    if request.stream:
        return StreamingResponse(
            _stream_response(answer, request_id),
            media_type="text/event-stream",
        )

    payload = {
        "id": request_id,
        "object": "chat.completion",
        "created": created,
        "model": MODEL_ID,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "nbdag_meta": {
            "retrieval_status": retrieval_status,
            "retrieval_detail": retrieval_detail,
            "retrieval_chunks": [chunk.model_dump() for chunk in retrieval_chunks],
        },
    }
    return JSONResponse(payload)
