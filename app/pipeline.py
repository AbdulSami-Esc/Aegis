import logging
from pipecat import Pipeline
from pipecat import PipelineTask
from pipecat import PipelineRunner
from pipecat import (
    FastAPIWebSocketTransport,
    FastAPIWebSocketParams
)
from pipecat import ProtobufFrameSerializer

# (Assuming FrameLogger is already defined above this in the same file)

logger = logging.getLogger(__name__)

async def run_call(websocket):
    ##Build transport params (The Loading Dock Rules)
    params = FastAPIWebSocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,##I made bothj true as we are doing full duplex audio
        serializer=ProtobufFrameSerializer()
    )
    
    #Create the transport from the websocket (The Loading Dock)
    transport = FastAPIWebSocketTransport(
        websocket=websocket,
        params=params
    )
    
    #Build the Pipeline (The Conveyor Belt)
    pipeline = Pipeline([
        transport.input(),   # Takes bytes from WebSocket, turns to Frames
        FrameLogger(),       # Inspects the Frames
        transport.output()   # Turns Frames back to bytes, sends to WebSocket
    ])
    
    #Create the Task and Runner (The Motor and the Manager)
    task = PipelineTask(pipeline)
    runner = PipelineRunner()
    
    #Register Event Handlers (Dealing with hangups)
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected to the factory!")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client hung up! Stopping the belt.")
        await task.cancel() # Stops the asyncio task so it doesn't run forever
        
    #Run the task wrapped in try/finally
    try:
        logger.info("Starting the conveyor belt...")
        # This await keeps the function running until task.cancel() is called
        await runner.run(task)
    finally:
        # This always runs when the function ends, even if it crashes
        logger.info("Cleaning up the factory floor...")