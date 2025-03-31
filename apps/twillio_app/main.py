# Standard library imports
import os
import sys

from dotenv import load_dotenv

# Third-party imports
from fastapi import FastAPI
from loguru import logger
from pyngrok import ngrok

from vocode.logging import configure_pretty_logging
from vocode.streaming.models.agent import ChatGPTAgentConfig, OPENAI_GPT_4_O_MODEL_NAME
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import WaveSynthesizerConfig
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.telephony.config_manager.in_memory_config_manager import InMemoryConfigManager
from vocode.streaming.telephony.conversation.outbound_call import OutboundCall
from vocode.streaming.telephony.server.base import TelephonyServer, TwilioInboundCallConfig

from fastapi import APIRouter

# if running from python, this will load the local .env
# docker-compose will load the .env file by itself
load_dotenv()

configure_pretty_logging()

app = FastAPI(docs_url=None)
config_manager = InMemoryConfigManager()
synt_config = WaveSynthesizerConfig.from_telephone_output_device()
synt_config.api_key = os.getenv("WAVES_API_KEY")

BASE_URL = os.getenv("BASE_URL")

if not BASE_URL:
    ngrok_auth = os.environ.get("NGROK_AUTH_TOKEN")
    if ngrok_auth is not None:
        ngrok.set_auth_token(ngrok_auth)
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else 3000

    # Open a ngrok tunnel to the dev server
    BASE_URL = ngrok.connect(port).public_url.replace("https://", "")
    logger.info('ngrok tunnel "{}" -> "http://127.0.0.1:{}"'.format(BASE_URL, port))

if not BASE_URL:
    raise ValueError("BASE_URL must be set in environment if not using pyngrok")

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        TwilioInboundCallConfig(
            url="/inbound_call",
            agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(text="Whats up, how are you doing"),
                prompt_preamble="Have a pleasant conversation about life",
                generate_responses=True,
                model_name=OPENAI_GPT_4_O_MODEL_NAME
            ),
            synthesizer_config=synt_config,
            twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),

        )
    ]
)

router = APIRouter()


@router.post("/make_call")
async def make_call():
    outbound_call = OutboundCall(
        base_url=BASE_URL,
        # TODO: move tophone to arguement
        to_phone="+918824916178",
        from_phone="+19253294640",
        config_manager=config_manager,
        agent_config=ChatGPTAgentConfig(
            initial_message=BaseMessage(text="What's up, How are you?"),
            prompt_preamble="Have a pleasant conversation about life",
            generate_responses=True,
            model_name=OPENAI_GPT_4_O_MODEL_NAME
        ),
        telephony_config=TwilioConfig(
            account_sid=os.environ["TWILIO_ACCOUNT_SID"],
            auth_token=os.environ["TWILIO_AUTH_TOKEN"],
        ),
        synthesizer_config=synt_config
    )

    # For testing purposes: block until you press enter on the server console.
    # NOTE: In a production endpoint, you would typically remove this blocking call.
    print("to start call...")

    # Start the outbound call asynchronously and get the conversation ID
    await outbound_call.start()
    return {"conversation_id"}


app.include_router(telephony_server.get_router())
app.include_router(router)
