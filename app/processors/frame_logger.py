import time
import logging
from pipecat import FrameProcessor, FrameDirection

logger = logging.getLogger(__name__)

class FrameLogger(FrameProcessor):
    ##direction parameter would tell whether this is moving from mic to AI or AI to mic
    async def process_frame(self, frame, direction: FrameDirection):
        ##First safety check before a frame is checked
        await super().process_frame(frame, direction)
        
        current_time = time.perf_counter()
        frame_type = type(frame).__name__

        ##Checking if the frame object contains audio material
        if hasattr(frame, "audio"):
            ##Count the exact number of butes in the audio payload
            audio_length = len(frame.audio)
            logger.info(f"[{current_time:.3f}] {direction.name}: {frame_type} | Size: {audio_length} bytes")
        else:
            logger.info(f"[{current_time:.3f}] {direction.name}: {frame_type}")
        ##Hands the frame off to the next processor in the pipeline  
        await self.push_frame(frame, direction)