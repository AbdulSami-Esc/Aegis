import time
import logging
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import (
    TranscriptionFrame,
    InterimTranscriptionFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame
)

logger = logging.getLogger(__name__)

##this class watches every piece of data passing through,reacts only to the specific triggers
class SpeechLogger(FrameProcessor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.stop_time = None  ##We need to remember the exact time the user stopped speaking so we can compare it to the time final text arrives

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # Did the microphone operator hear a voice?
        if isinstance(frame, VADUserStartedSpeakingFrame):
            logger.info("🎙️ User started speaking...")

        # Did the microphone operator hear silence?
        elif isinstance(frame, VADUserStoppedSpeakingFrame):
            self.stop_time = time.perf_counter()
            logger.info("🛑 User stopped speaking. (Stopwatch started!)")

        # Are we getting live, changing guesses?
        elif isinstance(frame, InterimTranscriptionFrame):
            # Using logger.debug so it doesn't flood our main terminal output
            logger.debug(f"Draft text: {frame.text}")

        # Did we get the final locked-in sentence?
        elif isinstance(frame, TranscriptionFrame):
            if self.stop_time is not None:
                # Calculate the gap between silence and final text
                latency_sec = time.perf_counter() - self.stop_time
                latency_ms = latency_sec * 1000

                logger.info(f"✅ Final text: '{frame.text}' (Latency: {latency_ms:.0f} ms)")

                # Reset the stopwatch for the next sentence
                self.stop_time = None
            else:
                # Just in case we get text without a VAD stop frame
                logger.info(f"✅ Final text: '{frame.text}'")

        # Hand the frame to the next processor, or the pipeline stops here
        await self.push_frame(frame, direction)