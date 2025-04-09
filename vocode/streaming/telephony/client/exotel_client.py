import os
from typing import Dict, Optional

import aiohttp
import xmltodict
from loguru import logger
from vocode.streaming.models.telephony import ExotelConfig
from vocode.streaming.telephony.client.abstract_telephony_client import AbstractTelephonyClient
from vocode.streaming.utils.async_requester import AsyncRequestor


class ExotelBadRequestException(ValueError):
    pass


class ExotelException(ValueError):
    pass


class ExotelClient(AbstractTelephonyClient):
    def __init__(
            self,
            base_url: str,
            maybe_exotel_config: Optional[ExotelConfig] = None,
    ):
        self.exotel_config = maybe_exotel_config or ExotelConfig(
            account_sid=os.environ["EXOTEL_ACCOUNT_SID"],
            sub_domain=os.environ["EXOTEL_SUBDOMAIN"],
            api_key=os.environ["EXOTEL_API_KEY"],
            api_token=os.environ["EXOTEL_API_TOKEN"],
            caller_id=os.environ["EXOTEL_CALLER_ID"],
        )
        self.auth = aiohttp.BasicAuth(login=self.exotel_config.api_key, password=self.exotel_config.api_token)
        super().__init__(base_url=base_url)

    def get_telephony_config(self):
        return self.exotel_config

    @staticmethod
    def create_call_exotel(base_url, conversation_id, is_outbound: bool = False):
        return {"url": f"wss://{base_url}/connect_call/{conversation_id}"}

    async def create_call(
            self,
            conversation_id: str,
            to_phone: str,
            from_phone: str,
            record: bool = False,  # currently no-op
            digits: Optional[str] = None,  # currently no-op
            telephony_params: Optional[Dict[str, str]] = None,
    ) -> str:
        data = {
            'From': from_phone,
            'To': to_phone,
            'CallType': "trans",
            'CallerId': self.exotel_config.caller_id
        }
        async with AsyncRequestor().get_session().post(
                f'https://{self.exotel_config.sub_domain}/v1/Accounts/{self.exotel_config.account_sid}/Calls/connect',
                auth=self.auth,
                data=data
        ) as response:
            if not response.ok:
                if response.status == 400:
                    te = await response.text()
                    exotel_response = xmltodict.parse(te)

                    logger.warning(
                        f"Failed to create call: {exotel_response}"
                    )
                    raise ExotelBadRequestException(
                        "Telephony provider rejected call; this is usually due to a bad/malformed number. "
                    )
                else:
                    raise ExotelException(
                        f"Exotel failed to create call: {response.status} {response.reason}"
                    )
            xml_data = await response.text()
            exotel_response = xmltodict.parse(xml_data)
            call_sid = exotel_response['TwilioResponse']['Call']['Sid']
            return call_sid

    async def end_call(self, twilio_sid):
        pass