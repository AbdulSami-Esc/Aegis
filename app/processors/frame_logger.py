import logging
import time

from pipecat.frames.frames import AudioRawFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

logger = logging.getLogger(__name__)


class FrameLogger(FrameProcessor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._last_audio_time = None
        self._audio_count = 0
        self._max_gap_ms = 0.0
        self._window_start = time.perf_counter()

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        now = time.perf_counter()
        frame_type = type(frame).__name__

        if isinstance(frame, AudioRawFrame):
            gap_ms = 0.0
            if self._last_audio_time is not None:
                gap_ms = (now - self._last_audio_time) * 1000
            self._last_audio_time = now
            self._audio_count += 1
            self._max_gap_ms = max(self._max_gap_ms, gap_ms)

            logger.debug(
                f"{direction.name}: {frame_type} | {len(frame.audio)} bytes | gap {gap_ms:.1f} ms"
            )

            # One summary line per second instead of 50 lines
            if now - self._window_start >= 1.0:
                logger.info(
                    f"audio frames/s: {self._audio_count} | worst gap: {self._max_gap_ms:.1f} ms"
                )
                self._audio_count = 0
                self._max_gap_ms = 0.0
                self._window_start = now
        else:
            logger.info(f"{direction.name}: {frame_type}")

        await self.push_frame(frame, direction)