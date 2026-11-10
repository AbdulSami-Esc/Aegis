# TODO: imports (check docs for exact paths): FrameProcessor, FrameDirection,
#       TranscriptionFrame, InterimTranscriptionFrame,
#       VADUserStartedSpeakingFrame, VADUserStoppedSpeakingFrame

class SpeechLogger(FrameProcessor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # TODO: store the time when the user stopped speaking (None at the start)

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        # TODO: speech started -> log it
        # TODO: speech stopped -> remember perf_counter() and log it
        # TODO: interim text -> log text (DEBUG level, it arrives fast)
        # TODO: final text -> log text and (now - stop_time) in ms, then reset stop_time
        await self.push_frame(frame, direction)