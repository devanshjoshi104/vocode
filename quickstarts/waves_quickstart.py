import asyncio
import os
import signal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from vocode.helpers import create_streaming_microphone_input_and_speaker_output
from vocode.logging import configure_pretty_logging
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import WaveSynthesizerConfig
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.streaming.synthesizer.waves_synthesizer import WaveSynthesizer
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber

configure_pretty_logging()
load_dotenv()


class Settings(BaseSettings):
    """
    Settings for the streaming conversation quickstart.
    These parameters can be configured with environment variables.
    """

    openai_api_key: str = os.getenv("OPENAI_API_KEY")
    waves_api_key: str = os.getenv("WAVES_API_KEY")
    deepgram_api_key: str = os.getenv("DEEPGRAM_API_KEY")



    # This means a .env file can be used to overload these settings
    # ex: "OPENAI_API_KEY=my_key" will set openai_api_key over the default above
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

async def main():
    (
        microphone_input,
        speaker_output,
    ) = create_streaming_microphone_input_and_speaker_output(
        use_default_devices=False,
    )
    waves_config = WaveSynthesizerConfig.from_output_device(speaker_output)
    waves_config.api_key = settings.waves_api_key
    waves_config.voice_id = "ananya"
    # waves_config.sampling_rate = SamplingRate.RATE_16000
    conversation = StreamingConversation(
        output_device=speaker_output,
        transcriber=DeepgramTranscriber(
            DeepgramTranscriberConfig.from_input_device(
                microphone_input,
                endpointing_config=PunctuationEndpointingConfig(),
                api_key=settings.deepgram_api_key,
            ),
        ),
        agent=ChatGPTAgent(
            ChatGPTAgentConfig(
                openai_api_key=settings.openai_api_key,
                initial_message=BaseMessage(text="What's up, How are you?"),
                prompt_preamble="""The AI is having a pleasant conversation about life""",
            )
        ),
        synthesizer=WaveSynthesizer(waves_config),
    )
    await conversation.start()
    print("Conversation started, press Ctrl+C to end")
    signal.signal(signal.SIGINT, lambda _0, _1: asyncio.create_task(conversation.terminate()))
    while conversation.is_active():
        chunk = await microphone_input.get_audio()
        conversation.receive_audio(chunk)


if __name__ == "__main__":
    asyncio.run(main())
