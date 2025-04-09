import os
import sys

from dotenv import load_dotenv

# Third-party imports
from fastapi import FastAPI
from loguru import logger
from pydantic import BaseModel
from pyngrok import ngrok

from vocode.logging import configure_pretty_logging
from vocode.streaming.models.agent import ChatGPTAgentConfig, OPENAI_GPT_4_O_MODEL_NAME, OPENAI_GPT_4_O_MINI_MODEL_NAME
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import WaveSynthesizerConfig
from vocode.streaming.models.telephony import TwilioConfig, ExotelConfig
from vocode.streaming.telephony.config_manager.in_memory_config_manager import InMemoryConfigManager
from vocode.streaming.telephony.conversation.outbound_call import OutboundCall
from vocode.streaming.telephony.server.base import TelephonyServer, TwilioInboundCallConfig, ExotelInboundCallConfig

from fastapi import APIRouter


load_dotenv()
from events_manager import EventsManager

configure_pretty_logging()

app = FastAPI(docs_url=None)
config_manager = InMemoryConfigManager()
synt_config = WaveSynthesizerConfig.from_exotel_output_device()
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

exotel_config = ExotelConfig(
    account_sid=os.environ["EXOTEL_ACCOUNT_SID"],
    sub_domain=os.environ["EXOTEL_SUBDOMAIN"],
    api_key=os.environ["EXOTEL_API_KEY"],
    api_token=os.environ["EXOTEL_API_TOKEN"],
    caller_id=os.environ["EXOTEL_CALLER_ID"],
)

agent_config = ChatGPTAgentConfig(
    initial_message=BaseMessage(text="Hey Mayank, What's up, How are you?"),
    prompt_preamble="Have a pleasant conversation about life",
    generate_responses=True,
    model_name=OPENAI_GPT_4_O_MINI_MODEL_NAME)

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    events_manager=EventsManager(),
    inbound_call_configs=[
        ExotelInboundCallConfig(
            url="/inbound_call",
            agent_config=agent_config,
            synthesizer_config=synt_config,
            exotel_config=exotel_config,
        )
    ]
)

router = APIRouter()


class MakeCallRequest(BaseModel):
    to_phone: str


@router.post("/make_call")
async def make_call(request: MakeCallRequest):
    outbound_call = OutboundCall(
        base_url=BASE_URL,
        to_phone=request.to_phone,
        from_phone=f"+91{exotel_config.caller_id}",
        config_manager=config_manager,
        agent_config=agent_config,
        telephony_config=exotel_config,
        synthesizer_config=synt_config
    )
    conversation_id = await outbound_call.start()
    return {"conversation_id": conversation_id}


app.include_router(telephony_server.get_router())
app.include_router(router)
