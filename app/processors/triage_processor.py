import logging

from pipecat.frames.frames import LLMContextFrame, StartFrame, TextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.triage.extractor import Extractor
from app.triage.fsm import TriageFSM
from app.triage.replier import Replier

logger = logging.getLogger(__name__)


class TriageProcessor(FrameProcessor):
    def __init__(self, extractor=None, replier=None, **kwargs):
        super().__init__(**kwargs)
        self._fsm = TriageFSM()
        self._extractor = extractor or Extractor()
        self._replier = replier or Replier()
        self._last_text = None
        self._last_question = ""

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # Always pass the frame on first, so the pipeline keeps working.
        await self.push_frame(frame, direction)

        if isinstance(frame, StartFrame):
            opening = self._fsm.opening().scripted_text
            self._last_question = opening
            logger.info("AEGIS: %s", opening)
            await self.push_frame(TextFrame(opening))

        elif isinstance(frame, LLMContextFrame) and direction == FrameDirection.DOWNSTREAM:
            text = self._latest_user_text(frame.context)
            if text and text != self._last_text and not self._fsm.is_finished:
                self._last_text = text
                await self._handle_turn(text)

    async def _handle_turn(self, text: str) -> None:
        update = await self._extractor.extract(text, self._fsm.record, self._last_question)
        directive = self._fsm.on_user_turn(text, update)
        reply = await self._replier.reply(directive, text)
        self._last_question = reply

        logger.info("PATIENT: %s", text)
        logger.info("STATE: %s | missing: %s", self._fsm.state.value, self._fsm.record.missing_fields())
        logger.info("AEGIS: %s", reply)

        await self.push_frame(TextFrame(reply))

    @staticmethod
    def _latest_user_text(context) -> str:
        """Return the text of the most recent user message in the context."""
        for message in reversed(context.get_messages()):
            if message.get("role") != "user":
                continue
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):  # list of parts like {"type": "text", "text": "..."}
                parts = [p.get("text", "") for p in content if isinstance(p, dict)]
                return " ".join(parts).strip()
        return ""