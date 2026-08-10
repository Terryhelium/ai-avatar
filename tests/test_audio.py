import io
import unittest
import wave

from kiosk_app.audio import audio_to_pcm16le, pcm16le_to_wav_bytes, pcm_chunk_stride_bytes


class PcmToWavTests(unittest.TestCase):
    def test_wraps_pcm_as_wav(self) -> None:
        pcm_bytes = b"\x00\x00\x01\x00\xff\x7f"
        wav_bytes = pcm16le_to_wav_bytes(pcm_bytes, sample_rate=16000)

        self.assertTrue(wav_bytes.startswith(b"RIFF"))
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            self.assertEqual(wav_file.getframerate(), 16000)
            self.assertEqual(wav_file.getnchannels(), 1)
            self.assertEqual(wav_file.readframes(3), pcm_bytes)

    def test_transcodes_audio_to_pcm16le(self) -> None:
        pcm_bytes = b"\x00\x00\x01\x00\xff\x7f"
        wav_bytes = pcm16le_to_wav_bytes(pcm_bytes, sample_rate=16000)

        transcoded = audio_to_pcm16le(wav_bytes, sample_rate=16000)

        self.assertEqual(transcoded, pcm_bytes)

    def test_resamples_pcm_wav_without_ffmpeg(self) -> None:
        samples = []
        for index in range(22050):
            value = 12000 if index % 40 < 20 else -12000
            samples.append(value.to_bytes(2, "little", signed=True))
        wav_bytes = pcm16le_to_wav_bytes(b"".join(samples), sample_rate=22050)

        transcoded = audio_to_pcm16le(wav_bytes, sample_rate=16000)

        self.assertGreater(len(transcoded), 1000)
        self.assertAlmostEqual(len(transcoded), 16000 * 2, delta=16)

    def test_calculates_pcm_chunk_stride(self) -> None:
        self.assertEqual(
            pcm_chunk_stride_bytes(sample_rate=16000, chunk_size_ms=10, chunk_interval=10),
            1920,
        )


if __name__ == "__main__":
    unittest.main()
