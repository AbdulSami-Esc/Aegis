# TODO: import SileroVADAnalyzer, VADParams, DeepgramSTTService,
#       LLMContext, LLMContextAggregatorPair, LLMUserAggregatorParams
#       (paths are in the speech-input and Deepgram docs pages)

# Inside run_call, before building the pipeline:
# TODO: vad = Silero VAD with sample_rate from settings (what must it be?)
# TODO: stt = Deepgram service, key from settings, interim_results on
# TODO: build the context and the aggregator pair with vad in the user params
# TODO: new order: transport.input() -> stt -> user aggregator -> SpeechLogger -> FrameLogger -> transport.output()
# TODO: confirm the order against the docs (where must STT sit relative to VAD?)