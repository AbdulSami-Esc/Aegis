import logging
##It accepts connection then hands the caller to run_call
##It catches hang ups and unexpected errors
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app import pipeline as pipeline_module
from app.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Voice Agent Server is running"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("New WebSocket connection accepted.")

    try:
        await pipeline_module.run_call(websocket)
    except WebSocketDisconnect:
        logger.info("Client disconnected from the WebSocket route.")
    except Exception:
        logger.exception("Call failed with an unexpected error.")