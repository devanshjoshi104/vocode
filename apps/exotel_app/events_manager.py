import os
import typing
from typing import Optional

# Import all required utils
from vocode.streaming.models.events import Event, EventType
from vocode.streaming.models.transcript import TranscriptCompleteEvent
from vocode.streaming.utils import events_manager

import httpx

class EventsManager(events_manager.EventsManager):

    def __init__(self):
        super().__init__(subscriptions=[EventType.TRANSCRIPT_COMPLETE])

    async def handle_event(self, event: Event):
        if event.type == EventType.TRANSCRIPT_COMPLETE:
            transcript_complete_event = typing.cast(TranscriptCompleteEvent, event)

            data = {
                "conversation_id": transcript_complete_event.conversation_id,
                "transcript": transcript_complete_event.transcript.to_string()
            }
            # transcript to be used for post-processing
