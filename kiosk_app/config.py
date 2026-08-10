from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field


def _get_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _get_env_int(name: str, default: int) -> int:
    return int(_get_env(name, str(default)))


def _get_env_float(name: str, default: float) -> float:
    return float(_get_env(name, str(default)))


def _get_env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "")
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


def _get_env_int_list(name: str, default: list[int]) -> list[int]:
    return [int(item) for item in _get_env_list(name, [str(value) for value in default])]


def _get_env_text_int(name: str, default: int) -> int:
    raw = _get_env(name, str(default))
    digits = re.findall(r"\d+", raw)
    return int(digits[0]) if digits else default


def _get_env_json_dict(name: str, default: dict[str, str]) -> dict[str, str]:
    raw = os.getenv(name, "")
    if not raw:
        return default
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError(f"{name} must be a JSON object")
        return {str(key): str(value) for key, value in data.items()}
    except json.JSONDecodeError:
        # Accept a relaxed form like {spk_id:中文女} to make remote env writing safer.
        stripped = raw.strip().strip("{}").strip()
        if not stripped:
            return {}
        items: dict[str, str] = {}
        for pair in stripped.split(","):
            if ":" not in pair:
                raise ValueError(f"{name} must be a JSON object or key:value pairs")
            key, value = pair.split(":", 1)
            items[key.strip().strip("'\"")] = value.strip().strip("'\"")
        return items


@dataclass(slots=True)
class Settings:
    app_host: str = field(default_factory=lambda: _get_env("APP_HOST", "0.0.0.0"))
    app_port: int = field(default_factory=lambda: _get_env_int("APP_PORT", 18080))
    request_timeout_seconds: float = field(
        default_factory=lambda: _get_env_float("REQUEST_TIMEOUT_SECONDS", 30.0)
    )
    ragflow_timeout_seconds: float = field(
        default_factory=lambda: _get_env_float("RAGFLOW_TIMEOUT_SECONDS", 10.0)
    )
    ollama_timeout_seconds: float = field(
        default_factory=lambda: _get_env_float("OLLAMA_TIMEOUT_SECONDS", 20.0)
    )
    cosyvoice_timeout_seconds: float = field(
        default_factory=lambda: _get_env_float("COSYVOICE_TIMEOUT_SECONDS", 60.0)
    )
    tts_max_chars: int = field(default_factory=lambda: _get_env_text_int("TTS_MAX_CHARS", 90))
    funasr_timeout_seconds: float = field(
        default_factory=lambda: _get_env_float("FUNASR_TIMEOUT_SECONDS", 20.0)
    )
    metahuman_timeout_seconds: float = field(
        default_factory=lambda: _get_env_float("METAHUMAN_TIMEOUT_SECONDS", 10.0)
    )

    ragflow_url: str = field(
        default_factory=lambda: _get_env(
            "RAGFLOW_URL",
            "http://10.19.26.148:19003/api/v1/retrieval",
        )
    )
    ragflow_token: str = field(default_factory=lambda: _get_env("RAGFLOW_TOKEN", ""))
    ragflow_dataset_ids: list[str] = field(
        default_factory=lambda: _get_env_list("RAGFLOW_DATASET_IDS", [])
    )
    ragflow_top_k: int = field(default_factory=lambda: _get_env_int("RAGFLOW_TOP_K", 3))

    ollama_url: str = field(
        default_factory=lambda: _get_env(
            "OLLAMA_URL",
            "http://10.19.26.153:11434/v1/chat/completions",
        )
    )
    ollama_model: str = field(default_factory=lambda: _get_env("OLLAMA_MODEL", "qwen2.5:7b"))
    ollama_keep_alive: str = field(
        default_factory=lambda: _get_env("OLLAMA_KEEP_ALIVE", "0s")
    )
    ollama_max_tokens: int = field(
        default_factory=lambda: _get_env_int("OLLAMA_MAX_TOKENS", 1200)
    )
    ollama_temperature: float = field(
        default_factory=lambda: _get_env_float("OLLAMA_TEMPERATURE", 0.3)
    )

    cosyvoice_url: str = field(
        default_factory=lambda: _get_env(
            "COSYVOICE_URL",
            "http://10.19.26.153:50000/inference_sft",
        )
    )
    cosyvoice_text_field: str = field(
        default_factory=lambda: _get_env("COSYVOICE_TEXT_FIELD", "tts_text")
    )
    cosyvoice_extra_form_json: dict[str, str] = field(
        default_factory=lambda: _get_env_json_dict(
            "COSYVOICE_EXTRA_FORM_JSON",
            {"spk_id": "中文男"},
        )
    )
    funasr_ws_url: str = field(
        default_factory=lambda: _get_env(
            "FUNASR_WS_URL",
            "ws://10.19.26.153:10096",
        )
    )
    funasr_mode: str = field(default_factory=lambda: _get_env("FUNASR_MODE", "offline"))
    funasr_chunk_size: list[int] = field(
        default_factory=lambda: _get_env_int_list("FUNASR_CHUNK_SIZE", [0, 10, 5])
    )
    funasr_chunk_interval: int = field(
        default_factory=lambda: _get_env_int("FUNASR_CHUNK_INTERVAL", 10)
    )
    funasr_sample_rate: int = field(
        default_factory=lambda: _get_env_int("FUNASR_SAMPLE_RATE", 16000)
    )
    tts_sample_rate: int = field(default_factory=lambda: _get_env_int("TTS_SAMPLE_RATE", 22050))
    metahuman_enabled: bool = field(
        default_factory=lambda: _get_env_bool("METAHUMAN_ENABLED", True)
    )
    metahuman_offer_url: str = field(
        default_factory=lambda: _get_env(
            "METAHUMAN_OFFER_URL",
            "http://10.19.26.153:8010/offer",
        )
    )
    metahuman_ws_url: str = field(
        default_factory=lambda: _get_env(
            "METAHUMAN_WS_URL",
            "ws://10.19.26.153:8001/humanecho",
        )
    )

    kiosk_title: str = field(
        default_factory=lambda: _get_env("KIOSK_TITLE", "档案馆接待助手")
    )
    system_prompt: str = field(
        default_factory=lambda: _get_env(
            "SYSTEM_PROMPT",
            (
                "你是档案馆门口接待机的智能助手。"
                "用简洁、自然、礼貌的中文回答问题。"
                "优先基于知识库内容作答；如果知识库无法支撑结论，就明确说明不知道，"
                "不要编造馆藏、制度、流程或开放时间。"
            ),
        )
    )
    static_dir: str = field(default_factory=lambda: _get_env("STATIC_DIR", "kiosk_app/static"))


def load_settings() -> Settings:
    return Settings()
