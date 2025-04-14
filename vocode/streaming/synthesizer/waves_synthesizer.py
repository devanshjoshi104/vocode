import audioop
import hashlib

from vocode.streaming.models.synthesizer import  WaveSynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer, SynthesisResult
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.audio import AudioEncoding
from typing import AsyncGenerator
from pydub import AudioSegment

import requests
import asyncio
import io
import wave


class WaveSynthesizer(BaseSynthesizer[WaveSynthesizerConfig]):
    def __init__(self, synthesizer_config: WaveSynthesizerConfig):
        super().__init__(synthesizer_config)
        self.api_key = synthesizer_config.api_key
        self.voice_id = synthesizer_config.voice_id
        self.speed = synthesizer_config.speed
        self.sample_rate = synthesizer_config.sampling_rate
        self.audio_encoding = synthesizer_config.audio_encoding
        self.num_channels = 1

    @classmethod
    def get_voice_identifier(cls, synthesizer_config: WaveSynthesizerConfig):
        hashed_api_key = hashlib.sha256(f"{synthesizer_config.api_key}".encode("utf-8")).hexdigest()
        return ":".join(
            (
                "waves",
                hashed_api_key,
                str(synthesizer_config.voice_id)
            )
        )

    async def create_speech_uncached(
            self,
            message: BaseMessage,
            chunk_size: int,
            is_first_text_chunk: bool = False,
            is_sole_text_chunk: bool = False,
    ) -> SynthesisResult:
        loop = asyncio.get_event_loop()
        response_bytes = await loop.run_in_executor(None, self.call_wave_api, message.text)

        async def chunk_generator() -> AsyncGenerator[SynthesisResult.ChunkResult, None]:
            with wave.open(io.BytesIO(response_bytes), "rb") as wav:
                buffer = wav.readframes(wav.getnframes())

                # converting to mulaw encoding for telephony
                if self.audio_encoding == AudioEncoding.MULAW:
                    buffer = audioop.lin2ulaw(
                        buffer, 2
                    )
                for i in range(0, len(buffer), chunk_size):
                    is_last = i + chunk_size >= len(buffer)
                    yield SynthesisResult.ChunkResult(
                        chunk=buffer[i: i + chunk_size],
                        is_last_chunk=is_last
                    )

        return SynthesisResult(
            chunk_generator=chunk_generator(),
            get_message_up_to=lambda seconds: message.text  # Since no timestamps from Waves
        )

    def call_wave_api(self, text):
        url = "https://waves-api.smallest.ai/api/v1/lightning/get_speech"
        payload = {
            "voice_id": self.voice_id,
            "text": text,
            "speed": self.speed,
            "sample_rate": 8000,  # API supports only 8000
            "add_wav_header": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Waves API error: {response.status_code} - {response.text}")

        if self.sample_rate == 8000:
            return response.content

        # Convert to target sample rate using pydub
        original = AudioSegment.from_file(io.BytesIO(response.content), format="wav")
        converted = original.set_frame_rate(self.sample_rate)

        out_buffer = io.BytesIO()
        converted.export(out_buffer, format="wav")
        return out_buffer.getvalue()
