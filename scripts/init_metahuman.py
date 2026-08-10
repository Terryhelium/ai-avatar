from __future__ import annotations

import glob
import re
from pathlib import Path


ROOT = Path("/root/metahuman-stream")
TTSREAL_PATH = ROOT / "ttsreal.py"
LIPREAL_PATH = ROOT / "lipreal.py"
APP_PATH = ROOT / "app.py"
WEB_GLOB = str(ROOT / "web" / "*.html")

COSYVOICE_CLASS = """
class CosyVoiceTTS(BaseTTS):
    def __init__(self, opt, parent):
        super().__init__(opt, parent)
        self.api_url = "http://10.19.26.153:50000/inference_sft"
        self.spk_id = "中文男"
        self.source_sample_rate = 22050

    def txt_to_audio(self, msg):
        t = time.time()
        try:
            resp = requests.post(
                self.api_url,
                data={"tts_text": msg, "spk_id": self.spk_id},
                timeout=30,
            )
            if resp.status_code != 200:
                print(f"[CosyVoiceTTS] HTTP {resp.status_code}")
                return

            stream = np.frombuffer(resp.content, dtype=np.int16).astype(np.float32)
            if stream.size == 0:
                print("[CosyVoiceTTS] Empty PCM response")
                return

            stream /= 32767.0
            if self.source_sample_rate != self.sample_rate:
                stream = resampy.resample(
                    x=stream,
                    sr_orig=self.source_sample_rate,
                    sr_new=self.sample_rate,
                )

            print(f"[CosyVoiceTTS] {len(stream)} samples, {time.time() - t:.2f}s")
            idx = 0
            while idx + self.chunk <= len(stream):
                self.parent.put_audio_frame(stream[idx : idx + self.chunk])
                idx += self.chunk
        except Exception as exc:
            print(f"[CosyVoiceTTS] Error: {exc}")
""".strip()

HUMANCHAT_OLD = """@sockets.route('/humanchat')
def chat_socket(ws):
    if not ws:
        print('未建立连接！')
        return 'Please use WebSocket'
    else:
        while True:
            message = ws.receive()           
            if len(message)==0:
                return '输入信息为空'
            else:
                res=llm_response(message)                           
                nerfreal.put_msg_txt(res)"""

HUMANCHAT_NEW = """@sockets.route('/humanchat')
def chat_socket(ws):
    if not ws:
        print('未建立连接！')
        return 'Please use WebSocket'
    else:
        print('数字人 WebSocket 已连接 (等待 Fay 输入)...')
        while True:
            message = ws.receive()
            if not message or len(message) == 0:
                return '输入信息为空'
            else:
                print(f'数字人收到文本: {message[:50]}...')
                nerfreal.put_msg_txt(message)"""


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def patch_ttsreal() -> None:
    content = TTSREAL_PATH.read_text(encoding="utf-8")
    updated = re.sub(
        r"class CosyVoiceTTS\(BaseTTS\):.*\Z",
        COSYVOICE_CLASS,
        content,
        flags=re.S,
    )
    if updated == content:
        updated = content.rstrip() + "\n\n" + COSYVOICE_CLASS + "\n"
    _write(TTSREAL_PATH, updated)


def patch_lipreal() -> None:
    content = LIPREAL_PATH.read_text(encoding="utf-8")
    updated = content.replace(
        "from ttsreal import EdgeTTS,VoitsTTS,XTTS",
        "from ttsreal import EdgeTTS,VoitsTTS,XTTS,CosyVoiceTTS",
    )
    updated = updated.replace(
        """        elif opt.tts == "xtts":
            self.tts = XTTS(opt,self)""",
        """        elif opt.tts == "xtts":
            self.tts = XTTS(opt,self)
        elif opt.tts == "cosyvoice":
            self.tts = CosyVoiceTTS(opt,self)""",
    )
    _write(LIPREAL_PATH, updated)


def patch_web_files() -> None:
    for html_path in glob.glob(WEB_GLOB):
        path = Path(html_path)
        content = path.read_text(encoding="utf-8")
        updated = content.replace(":8000/humanchat", ":8001/humanchat").replace(
            ":8000/humanecho",
            ":8001/humanecho",
        )
        if updated != content:
            _write(path, updated)


def patch_app() -> None:
    content = APP_PATH.read_text(encoding="utf-8")
    updated = content

    if 'appasync.router.add_post("/offer", offer)' not in updated:
        updated = updated.replace(
            'appasync.router.add_post("/human", human)',
            'appasync.router.add_post("/human", human)\n    appasync.router.add_post("/offer", offer)',
        )

    if "llm_response(message)" in updated:
        updated = updated.replace(HUMANCHAT_OLD, HUMANCHAT_NEW)

    _write(APP_PATH, updated)


def main() -> None:
    patch_ttsreal()
    patch_lipreal()
    patch_web_files()
    patch_app()
    print("All patches applied")


if __name__ == "__main__":
    main()
