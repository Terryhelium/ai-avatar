from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
import websockets

from kiosk_app.audio import audio_to_pcm16le, pcm16le_to_wav_bytes, pcm_chunk_stride_bytes
from kiosk_app.config import Settings
from kiosk_app.models import ChatTurn, RetrievalChunk

logger = logging.getLogger(__name__)


class ServiceError(RuntimeError):
    """Raised when an upstream service request fails."""


@dataclass(slots=True)
class OrchestratedReply:
    answer: str
    retrieval_chunks: list[RetrievalChunk]
    retrieval_status: str
    retrieval_detail: str | None
    audio_base64: str | None
    audio_mime_type: str | None
    timings_ms: dict[str, int]
    metahuman_dispatched: bool


@dataclass(slots=True)
class RetrievalResult:
    chunks: list[RetrievalChunk]
    status: str
    detail: str | None = None


class RAGFlowClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http_client = http_client

    async def search(self, question: str) -> RetrievalResult:
        if not self._settings.ragflow_dataset_ids or not self._settings.ragflow_token:
            return RetrievalResult(chunks=[], status="disabled", detail="missing-config")

        try:
            response = await self._http_client.post(
                self._settings.ragflow_url,
                headers={
                    "Authorization": f"Bearer {self._settings.ragflow_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "question": question,
                    "dataset_ids": self._settings.ragflow_dataset_ids,
                    "top_k": self._settings.ragflow_top_k,
                },
                timeout=self._settings.ragflow_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != 0:
                detail = str(payload.get("message") or f"code:{payload.get('code')}")
                return RetrievalResult(chunks=[], status="error", detail=detail)
        except httpx.HTTPError as exc:
            detail = str(exc).strip() or exc.__class__.__name__
            return RetrievalResult(chunks=[], status="error", detail=detail)

        chunks = payload.get("data", {}).get("chunks", [])
        items = [
            RetrievalChunk(
                content=chunk.get("content", "").strip(),
                score=chunk.get("similarity"),
            )
            for chunk in chunks
            if chunk.get("content")
        ]
        if items:
            return RetrievalResult(chunks=items, status="hit")
        return RetrievalResult(chunks=[], status="miss")


class OllamaClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http_client = http_client

    async def answer(
        self,
        question: str,
        *,
        history: list[ChatTurn],
        retrieval_chunks: list[RetrievalChunk],
    ) -> str:
        prompt = self._settings.system_prompt
        if retrieval_chunks:
            context = "\n\n".join(chunk.content for chunk in retrieval_chunks[:3])[:2500]
            prompt += (
                "\n\n以下是知识库检索结果，请优先基于它们回答：\n"
                f"---\n{context}\n---"
            )

        messages: list[dict[str, str]] = [{"role": "system", "content": prompt}]
        for turn in history[-4:]:
            messages.append({"role": turn.role, "content": turn.content})
        messages.append({"role": "user", "content": question})

        response = await self._http_client.post(
            self._settings.ollama_url,
            json={
                "model": self._settings.ollama_model,
                "messages": messages,
                "keep_alive": self._settings.ollama_keep_alive,
                "temperature": self._settings.ollama_temperature,
                "max_tokens": self._settings.ollama_max_tokens,
                "user": "reception-kiosk",
            },
            timeout=self._settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        try:
            return payload["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ServiceError("Ollama response format is invalid") from exc


class CosyVoiceClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http_client = http_client

    async def synthesize(self, text: str) -> tuple[str, str]:
        form_data = dict(self._settings.cosyvoice_extra_form_json)
        form_data[self._settings.cosyvoice_text_field] = text

        response = await self._http_client.post(
            self._settings.cosyvoice_url,
            data=form_data,
            timeout=self._settings.cosyvoice_timeout_seconds,
        )
        response.raise_for_status()
        wav_bytes = pcm16le_to_wav_bytes(
            response.content,
            sample_rate=self._settings.tts_sample_rate,
        )
        audio_base64 = base64.b64encode(wav_bytes).decode("ascii")
        return audio_base64, "audio/wav"


class FunASRClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def transcribe(self, audio_bytes: bytes, *, wav_name: str = "microphone") -> str:
        try:
            pcm_bytes = await asyncio.to_thread(
                audio_to_pcm16le,
                audio_bytes,
                sample_rate=self._settings.funasr_sample_rate,
            )
            stride = pcm_chunk_stride_bytes(
                sample_rate=self._settings.funasr_sample_rate,
                chunk_size_ms=self._settings.funasr_chunk_size[1],
                chunk_interval=self._settings.funasr_chunk_interval,
            )
            transcript = ""
            async with websockets.connect(
                self._settings.funasr_ws_url,
                open_timeout=self._settings.funasr_timeout_seconds,
                close_timeout=self._settings.funasr_timeout_seconds,
                max_size=None,
            ) as websocket:
                await websocket.send(
                    json.dumps(
                        {
                            "mode": self._settings.funasr_mode,
                            "chunk_size": self._settings.funasr_chunk_size,
                            "encoder_chunk_look_back": 4,
                            "decoder_chunk_look_back": 1,
                            "chunk_interval": self._settings.funasr_chunk_interval,
                            "wav_name": wav_name,
                            "is_speaking": True,
                        }
                    )
                )
                for offset in range(0, len(pcm_bytes), stride):
                    await websocket.send(pcm_bytes[offset : offset + stride])
                await websocket.send(json.dumps({"is_speaking": False}))

                deadline = time.monotonic() + self._settings.funasr_timeout_seconds
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                    except TimeoutError:
                        break
                    if isinstance(message, bytes):
                        continue
                    payload = json.loads(message)
                    text = str(payload.get("text", "")).strip()
                    if text:
                        transcript = text
                    if payload.get("mode") in {"offline", "2pass-offline"}:
                        break
        except Exception as exc:  # noqa: BLE001
            raise ServiceError(f"FunASR request failed: {exc}") from exc

        if not transcript:
            raise ServiceError("FunASR returned empty transcription")
        return transcript


class MetahumanClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http_client = http_client

    async def offer(self, payload: dict[str, str]) -> dict[str, str]:
        response = await self._http_client.post(
            self._settings.metahuman_offer_url,
            json=payload,
            timeout=self._settings.metahuman_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ServiceError("Metahuman offer response format is invalid")
        return {
            "sdp": str(data["sdp"]),
            "type": str(data["type"]),
        }

    async def dispatch_text(self, text: str) -> None:
        if not text.strip():
            return
        async with websockets.connect(
            self._settings.metahuman_ws_url,
            open_timeout=self._settings.metahuman_timeout_seconds,
            close_timeout=self._settings.metahuman_timeout_seconds,
        ) as websocket:
            await websocket.send(text)


class Orchestrator:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http_client = http_client
        self._ragflow = RAGFlowClient(settings, http_client)
        self._ollama = OllamaClient(settings, http_client)
        self._cosyvoice = CosyVoiceClient(settings, http_client)
        self._funasr = FunASRClient(settings)
        self._metahuman = MetahumanClient(settings, http_client)

    async def reply(
        self,
        question: str,
        *,
        history: list[ChatTurn],
        synthesize_audio: bool,
    ) -> OrchestratedReply:
        timings_ms: dict[str, int] = {}

        start = time.perf_counter()
        retrieval = await self._ragflow.search(question)
        timings_ms["ragflow"] = _elapsed_ms(start)

        start = time.perf_counter()
        answer = await self._ollama.answer(
            question,
            history=history,
            retrieval_chunks=retrieval.chunks,
        )
        timings_ms["ollama"] = _elapsed_ms(start)
        speech_text = _build_speech_text(answer, max_chars=self._settings.tts_max_chars)

        metahuman_dispatched = False
        if self._settings.metahuman_enabled and speech_text:
            start = time.perf_counter()
            try:
                await self._metahuman.dispatch_text(speech_text)
                metahuman_dispatched = True
            except Exception:  # noqa: BLE001
                metahuman_dispatched = False
            timings_ms["metahuman"] = _elapsed_ms(start)

        audio_base64 = None
        audio_mime_type = None
        if synthesize_audio and speech_text:
            start = time.perf_counter()
            try:
                audio_base64, audio_mime_type = await self._cosyvoice.synthesize(speech_text)
            except Exception as exc:  # noqa: BLE001
                logger.warning("CosyVoice synthesis failed: %s", exc.__class__.__name__)
            timings_ms["cosyvoice"] = _elapsed_ms(start)

        return OrchestratedReply(
            answer=answer,
            retrieval_chunks=retrieval.chunks,
            retrieval_status=retrieval.status,
            retrieval_detail=retrieval.detail,
            audio_base64=audio_base64,
            audio_mime_type=audio_mime_type,
            timings_ms=timings_ms,
            metahuman_dispatched=metahuman_dispatched,
        )

    async def health(self) -> list[dict[str, str | bool]]:
        results: list[dict[str, str | bool]] = []
        results.append(await self._health_funasr())
        results.append(await self._health_ragflow())
        results.append(await self._health_ollama())
        results.append(await self._health_cosyvoice())
        results.append(await self._health_metahuman())
        return results

    async def transcribe(self, audio_bytes: bytes, *, wav_name: str = "microphone") -> str:
        return await self._funasr.transcribe(audio_bytes, wav_name=wav_name)

    async def _health_funasr(self) -> dict[str, str | bool]:
        try:
            async with websockets.connect(
                self._settings.funasr_ws_url,
                open_timeout=3,
                close_timeout=3,
                max_size=None,
            ):
                return {"name": "funasr", "ok": True, "detail": "ws:open"}
        except Exception as exc:  # noqa: BLE001
            return {"name": "funasr", "ok": False, "detail": exc.__class__.__name__}

    async def _health_ragflow(self) -> dict[str, str | bool]:
        if not self._settings.ragflow_dataset_ids or not self._settings.ragflow_token:
            return {"name": "ragflow", "ok": False, "detail": "missing-config"}
        try:
            response = await self._http_client.post(
                self._settings.ragflow_url,
                headers={
                    "Authorization": f"Bearer {self._settings.ragflow_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "question": "health check",
                    "dataset_ids": self._settings.ragflow_dataset_ids,
                    "top_k": 1,
                },
            )
            response.raise_for_status()
            payload = response.json()
            code = payload.get("code")
            return {
                "name": "ragflow",
                "ok": True,
                "detail": f"api:{code}",
            }
        except Exception as exc:  # noqa: BLE001
            return {"name": "ragflow", "ok": False, "detail": exc.__class__.__name__}

    async def _health_ollama(self) -> dict[str, str | bool]:
        try:
            response = await self._http_client.get(
                _origin_from_url(self._settings.ollama_url) + "/api/version",
                timeout=5,
            )
            response.raise_for_status()
            return {"name": "ollama", "ok": True, "detail": "api:version"}
        except Exception as exc:  # noqa: BLE001
            return {"name": "ollama", "ok": False, "detail": exc.__class__.__name__}

    async def _health_cosyvoice(self) -> dict[str, str | bool]:
        docs_url = _origin_from_url(self._settings.cosyvoice_url) + "/docs"
        try:
            response = await self._http_client.get(docs_url)
            response.raise_for_status()
            return {"name": "cosyvoice", "ok": True, "detail": "docs:200"}
        except Exception as exc:  # noqa: BLE001
            return {"name": "cosyvoice", "ok": False, "detail": exc.__class__.__name__}

    async def _health_metahuman(self) -> dict[str, str | bool]:
        if not self._settings.metahuman_enabled:
            return {"name": "metahuman", "ok": False, "detail": "disabled"}
        page_url = _origin_from_url(self._settings.metahuman_offer_url) + "/webrtcchat.html"
        try:
            response = await self._http_client.get(page_url)
            response.raise_for_status()
            return {"name": "metahuman", "ok": True, "detail": "page:200"}
        except Exception as exc:  # noqa: BLE001
            return {"name": "metahuman", "ok": False, "detail": exc.__class__.__name__}

    async def metahuman_offer(self, payload: dict[str, str]) -> dict[str, str]:
        if not self._settings.metahuman_enabled:
            raise ServiceError("Metahuman is disabled")
        return await self._metahuman.offer(payload)


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _origin_from_url(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _build_speech_text(answer: str, *, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", answer).strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    sentences = re.split(r"(?<=[。！？!?；;])", text)
    parts: list[str] = []
    total = 0
    for sentence in sentences:
        clean = sentence.strip()
        if not clean:
            continue
        next_total = total + len(clean)
        if parts and next_total > max_chars:
            break
        parts.append(clean)
        total = next_total
        if total >= max_chars:
            break

    if parts:
        compact = "".join(parts).strip()
        if len(compact) <= max_chars:
            return compact

    compact = text[:max_chars].rstrip("，,、；;：: ")
    if compact.endswith(("。", "！", "？", "!", "?")):
        return compact
    return f"{compact}。"
