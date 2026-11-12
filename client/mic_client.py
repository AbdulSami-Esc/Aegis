import asyncio

import sounddevice as sd
import websockets

from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame
from pipecat.serializers.protobuf import ProtobufFrameSerializer

URL = "ws://localhost:8000/ws"
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_MS = 20
CHUNK_FRAMES = SAMPLE_RATE * CHUNK_MS // 1000  # 320 samples = 640 bytes
##Records laptop microphone in 20ms chunks

async def main():
    serializer = ProtobufFrameSerializer()
    loop = asyncio.get_running_loop()
    mic_queue = asyncio.Queue(maxsize=50)
    ready=asyncio.Event()

    def enqueue(data: bytes):
        try:
            mic_queue.put_nowait(data)
        except asyncio.QueueFull:
            pass  # a live mic cannot wait, so drop the chunk

    def on_audio(indata, frames, time_info, status):
        # Runs on a separate audio thread, so hand the chunk to the event loop safely
        if status:
            print("Audio status:", status)
        loop.call_soon_threadsafe(enqueue, bytes(indata))

    async def send_mic(ws):
        print("Waiting for the server to be ready... (don't speak yet)")
        try:
            await asyncio.wait_for(ready.wait(), timeout=20)
        except asyncio.TimeoutError:
            print("No ready signal in 20 s, streaming anyway.")
        while not mic_queue.empty():
            mic_queue.get_nowait()  # discard stale audio recorded while waiting
        print("Ready. Speak now.")
        while True:
            chunk = await mic_queue.get()
            frame = OutputAudioRawFrame(
                audio=chunk, sample_rate=SAMPLE_RATE, num_channels=CHANNELS
            )
            await ws.send(await serializer.serialize(frame))

    async def receive(ws):
        speaker = None
        async for message in ws:
            ready.set()
            frame = await serializer.deserialize(message)
            if frame is None:
                continue
            print("Received:", type(frame).__name__)
            # Audio from the server arrives as InputAudioRawFrame
            if isinstance(frame, InputAudioRawFrame):
                if speaker is None:
                    speaker = sd.RawOutputStream(
                        samplerate=frame.sample_rate,
                        channels=frame.num_channels,
                        dtype="int16",
                    )
                    speaker.start()
                await asyncio.to_thread(speaker.write, frame.audio)

    async with websockets.connect(URL) as ws:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_FRAMES,
            callback=on_audio,
        ):
            print("Connected. Speak now. Press Ctrl+C to stop.")
            await asyncio.gather(send_mic(ws), receive(ws))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped.")