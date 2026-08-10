#!/usr/bin/env python3
"""验证 CosyVoice inference_zero_shot 推理是否正常"""
import sys, wave, os, requests

PROMPT_WAV = "/opt/cosyvoice/app/asset/zero_shot_prompt.wav"
OUTPUT_WAV = "/tmp/test_cosyvoice.wav"
API_URL    = "http://localhost:50000/inference_zero_shot"

resp = requests.post(
    API_URL,
    data={
        "tts_text": "你好，我是数字人助手，很高兴认识你。",
        "prompt_text": "希望你以后能够做的比我还好呦。"
    },
    files={"prompt_wav": open(PROMPT_WAV, "rb")},
    stream=True,
    timeout=60
)

print(f"HTTP 状态: {resp.status_code}")
pcm = b"".join(resp.iter_content(4096))
print(f"PCM 字节数: {len(pcm)}")

if len(pcm) > 1000:
    with wave.open(OUTPUT_WAV, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(pcm)
    print(f"✅ 成功，WAV 已保存: {os.path.getsize(OUTPUT_WAV)} bytes → {OUTPUT_WAV}")
    sys.exit(0)
else:
    print("❌ 失败，PCM 太少，查日志: tail -30 /var/log/cosyvoice.log")
    sys.exit(1)
