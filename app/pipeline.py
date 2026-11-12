import logging

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext  # verify with Step 1 below
from pipecat.processors.aggregators.llm_response_universal import (
    LLMUserAggregatorParams,
    LLMContextAggregatorPair,
)
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from app.config import get_settings
from app.processors.frame_logger import FrameLogger
from app.processors.speech_logger import SpeechLogger
##runs once for each caller to ensure data privacy is mantained
##Builds up eveyrthing from VAD to speech-to-text services an the belt
logger = logging.getLogger(__name__)


async def run_call(websocket):
    settings = get_settings()

    # Build the VAD Analyzer
    # Silero requires the sample rate to be exactly 8000 or 16000.
    vad_analyzer = SileroVADAnalyzer(
        sample_rate=settings.sample_rate,
        params=VADParams(min_volume=0.4,confidence=0.5 ),
    )

    # Build the Deepgram STT Service
    stt = DeepgramSTTService(
        api_key=settings.deepgram_api_key,
        settings=DeepgramSTTService.Settings(interim_results=True),
    )

    # Build the Context and Aggregator Pair
    context = LLMContext()

    user_aggregator_params = LLMUserAggregatorParams(
        vad_analyzer=vad_analyzer
    )

    aggregator_pair = LLMContextAggregatorPair(
        context,
        user_params=user_aggregator_params,
    )

    # Transport (same as Phase 1)
    params = FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        add_wav_header=False,
        serializer=ProtobufFrameSerializer(),
    )
    transport = FastAPIWebsocketTransport(websocket=websocket, params=params)

    # New Pipeline Order
    pipeline = Pipeline(
        [
            transport.input(),
            FrameLogger(label="before"),
            stt,
            SpeechLogger(),
            aggregator_pair.user(),
            FrameLogger(label="after"),
            transport.output(),
        ]
    )

    task = PipelineTask(pipeline)
    runner = PipelineRunner(handle_sigint=False)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected.")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client hung up. Cancelling the task.")
        await task.cancel()

    try:
        logger.info("Starting pipeline.")
        await runner.run(task)
    except Exception:
        logger.exception("Pipeline crashed.")
        raise
    finally:
        logger.info("Call cleanup finished.")