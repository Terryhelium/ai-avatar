from __future__ import annotations

import array
import io
import shutil
import subprocess
import wave


def pcm16le_to_wav_bytes(
    pcm_bytes: bytes,
    *,
    sample_rate: int = 22050,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Wrap raw PCM bytes in a WAV container for browser playback."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()


def audio_to_pcm16le(
    audio_bytes: bytes,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
) -> bytes:
    """Transcode uploaded audio bytes into raw PCM16LE for FunASR."""
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            pcm_bytes = wav_file.readframes(wav_file.getnframes())
            source_sample_rate = wav_file.getframerate()
            source_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()

        if sample_width == 2 and source_channels == channels and source_sample_rate == sample_rate:
            if not pcm_bytes:
                raise RuntimeError("wav input is empty")
            return pcm_bytes
        if sample_width == 2:
            if not pcm_bytes:
                raise RuntimeError("wav input is empty")
            return _resample_pcm16le_wav(
                pcm_bytes,
                source_sample_rate=source_sample_rate,
                source_channels=source_channels,
                target_sample_rate=sample_rate,
                target_channels=channels,
            )
        if not pcm_bytes:
            raise RuntimeError("wav input is empty")
    except wave.Error:
        pass

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise RuntimeError("ffmpeg is not installed and the uploaded audio is not PCM WAV")

    process = subprocess.run(
        [
            ffmpeg_path,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ac",
            str(channels),
            "-ar",
            str(sample_rate),
            "pipe:1",
        ],
        input=audio_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        message = process.stderr.decode("utf-8", errors="ignore").strip() or "ffmpeg failed"
        raise RuntimeError(message)
    if not process.stdout:
        raise RuntimeError("ffmpeg returned empty audio")
    return process.stdout


def _resample_pcm16le_wav(
    pcm_bytes: bytes,
    *,
    source_sample_rate: int,
    source_channels: int,
    target_sample_rate: int,
    target_channels: int,
) -> bytes:
    samples = array.array("h")
    samples.frombytes(pcm_bytes)
    frames = len(samples) // source_channels
    if frames == 0:
        raise RuntimeError("wav input is empty")

    mono: list[float] = []
    for frame_index in range(frames):
        offset = frame_index * source_channels
        frame = samples[offset : offset + source_channels]
        mono.append(sum(frame) / len(frame))

    if source_sample_rate != target_sample_rate:
        mono = _resample_mono_samples(mono, source_sample_rate, target_sample_rate)

    clipped = array.array(
        "h",
        (
            max(-32768, min(32767, int(round(sample))))
            for sample in mono
        ),
    )

    if target_channels == 1:
        return clipped.tobytes()

    expanded = array.array("h")
    for sample in clipped:
        expanded.extend([sample] * target_channels)
    return expanded.tobytes()


def _resample_mono_samples(
    samples: list[float],
    source_sample_rate: int,
    target_sample_rate: int,
) -> list[float]:
    if source_sample_rate == target_sample_rate or len(samples) < 2:
        return samples

    target_length = max(1, round(len(samples) * target_sample_rate / source_sample_rate))
    result: list[float] = []
    scale = source_sample_rate / target_sample_rate
    for index in range(target_length):
        position = index * scale
        left = int(position)
        right = min(left + 1, len(samples) - 1)
        fraction = position - left
        value = samples[left] * (1.0 - fraction) + samples[right] * fraction
        result.append(value)
    return result


def pcm_chunk_stride_bytes(
    *,
    sample_rate: int = 16000,
    chunk_size_ms: int = 10,
    chunk_interval: int = 10,
    sample_width: int = 2,
) -> int:
    return int(60 * chunk_size_ms / chunk_interval / 1000 * sample_rate * sample_width)
